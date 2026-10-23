"""Bounded, chunk-cached Edge TTS with explicit, renderable silence fallback."""
import math
import asyncio
from concurrent.futures import ThreadPoolExecutor
import subprocess
import threading
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4
import aiohttp
import edge_tts
from edge_tts.exceptions import EdgeTTSException
from imageio_ffmpeg import get_ffmpeg_exe
from config.settings import Settings
from providers.tts_text import clean_tts_text,has_speech,split_tts_text
from utils.atomic_io import discard_temp_file,replace_file_retry,write_json_atomic
from utils.cache import cache_key
from utils.diagnostics import Diagnostics
from utils.file_lock import file_lock
from utils.media import measured_audio_duration
from utils.word_timing import read_words,save_words,timing_source

_REQUESTS=threading.BoundedSemaphore(2)
RETRY_DELAYS=(2,4,8,16)  # Initial call plus at most four retries, per chunk/voice.


class TTSError(RuntimeError):
    pass


def audio_duration(path:Path)->float:
    duration=measured_audio_duration(path)
    if not math.isfinite(duration) or duration<=0:
        raise ValueError("Không đọc được độ dài audio hợp lệ.")
    return duration


def audio_metadata_path(path):
    return Path(path).with_suffix(".tts.json")


def create_silence(destination,duration,timeout=30):
    """Real decoded silence, not a zero-byte MP3 or an invented voice recording."""
    destination=Path(destination)
    if not math.isfinite(duration) or duration<=0: raise TTSError("Thời lượng im lặng không hợp lệ.")
    destination.parent.mkdir(parents=True,exist_ok=True)
    temporary=destination.with_name(uuid4().hex+".tmp.mp3")
    try:
        subprocess.run([get_ffmpeg_exe(),"-hide_banner","-loglevel","error","-y","-f","lavfi",
            "-i","anullsrc=r=24000:cl=mono","-t",str(duration),"-c:a","libmp3lame",str(temporary)],
            capture_output=True,check=True,timeout=timeout)
        audio_duration(temporary)
        replace_file_retry(temporary,destination)
    finally:
        discard_temp_file(temporary)
    return audio_duration(destination)


class EdgeTTSProvider:
    def __init__(self,settings:Settings,diagnostics:Diagnostics)->None:
        self.settings,self.diagnostics=settings,diagnostics

    def _chunk(self,text,voice,scene_id,index):
        key=cache_key({"text":text,"voice":voice,"rate":"+0%","version":2})
        cached=self.settings.cache_dir/"tts"/"chunks"/(key+".mp3")
        cached.parent.mkdir(parents=True,exist_ok=True)
        with file_lock(cached.with_suffix(".lock"),timeout=180):
            if cached.is_file():
                try:
                    audio_duration(cached)
                    return cached,None
                except Exception as error:
                    self.diagnostics.record_exception(error,f"TTS cảnh {scene_id}, đoạn {index}: cache hỏng")
            last=None
            for attempt in range(1,len(RETRY_DELAYS)+2):
                temporary=cached.with_name(uuid4().hex+".tmp.mp3")
                try:
                    with _REQUESTS:
                        request=edge_tts.Communicate(text,voice=voice,boundary="WordBoundary",
                            connect_timeout=int(self.settings.request_timeout_sec),receive_timeout=int(self.settings.request_timeout_sec))
                        boundaries=[]
                        if hasattr(request,"stream"):
                            async def collect():
                                with temporary.open("wb") as stream:
                                    async for event in request.stream():
                                        if event["type"]=="audio": stream.write(event["data"])
                                        elif event["type"]=="WordBoundary":
                                            boundaries.append({"text":event["text"],"start":event["offset"]/10_000_000,
                                                "end":(event["offset"]+event["duration"])/10_000_000})
                            async def bounded():
                                await asyncio.wait_for(collect(),timeout=max(30,self.settings.request_timeout_sec*3))
                            with ThreadPoolExecutor(max_workers=1) as worker:
                                worker.submit(asyncio.run,bounded()).result()
                        else:  # Compatible injected providers; old cache needs no new request.
                            request.save_sync(str(temporary))
                    audio_duration(temporary)
                    replace_file_retry(temporary,cached)
                    save_words(cached.with_suffix(".words.json"),text,audio_duration(cached),boundaries)
                    return cached,None
                except Exception as error:
                    last=self.diagnostics.redact(f"{type(error).__name__}: {error}")[:1500]
                    self.diagnostics.record_exception(error,
                        f"TTS lỗi ở cảnh {scene_id}; đoạn={index}; attempt={attempt}/5; voice={voice}; "
                        f"text_length={len(text)}; cleaned_text={text[:200]!r}")
                    retryable=isinstance(error,(EdgeTTSException,aiohttp.ClientError,TimeoutError,ConnectionError,OSError,ValueError))
                    if not retryable or attempt>len(RETRY_DELAYS): break
                finally:
                    discard_temp_file(temporary)
                time.sleep(RETRY_DELAYS[attempt-1])
            return None,last

    def _join(self,paths,destination):
        duration=max(1.5,sum(audio_duration(path) for path in paths))
        inputs=[arg for path in paths for arg in ("-i",str(path))]
        graph="".join(f"[{i}:a:0]" for i in range(len(paths)))+f"concat=n={len(paths)}:v=0:a=1,apad[out]"
        temporary=destination.with_name(uuid4().hex+".tmp.mp3")
        try:
            subprocess.run([get_ffmpeg_exe(),"-hide_banner","-loglevel","error","-y",*inputs,
                "-filter_complex",graph,"-map","[out]","-t",str(duration),"-ar","24000","-ac","1",
                "-c:a","libmp3lame",str(temporary)],capture_output=True,check=True,
                timeout=max(30,self.settings.request_timeout_sec))
            audio_duration(temporary)
            replace_file_retry(temporary,destination)
        finally:
            discard_temp_file(temporary)

    def synthesize(self,text,voice,destination,*,scene_id=None,duration_sec=None)->float:
        destination=Path(destination)
        scene_id=scene_id if scene_id is not None else destination.stem.removeprefix("scene_")
        clean=clean_tts_text(text)
        planned=max(1.5,float(duration_sec if duration_sec is not None else max(1.5,len(clean.split())/2.6)))
        destination.parent.mkdir(parents=True,exist_ok=True)
        warnings=[];parts=[];error=None;boundaries=[];cursor=0.;timing_sources=[]
        with file_lock(destination.with_suffix(".tts.lock"),timeout=1):
            if not has_speech(clean):
                warnings.append(f"cảnh {scene_id} không có giọng đọc: văn bản rỗng/chỉ có dấu câu sau khi làm sạch; dùng im lặng và caption.")
                create_silence(destination,planned,self.settings.request_timeout_sec)
                self.diagnostics.record(warnings[-1]+f" text_length={len(clean)}; cleaned_text={clean[:200]!r}; voice={voice}; attempt=0")
                parts=[{"index":1,"silent":True,"voice":None,"error":"Văn bản không có nội dung đọc."}]
                error=parts[0]["error"]
            else:
                chunks=split_tts_text(clean)
                fallback=self.settings.default_voice_fallback
                if fallback==voice:
                    fallback="vi-VN-HoaiMyNeural" if voice=="vi-VN-NamMinhNeural" else "vi-VN-NamMinhNeural"
                with TemporaryDirectory(prefix="tts-",dir=destination.parent) as work:
                    paths=[]
                    for index,chunk in enumerate(chunks,1):
                        path,last=self._chunk(chunk,voice,scene_id,index)
                        used=voice
                        if path is None:
                            used=fallback
                            path,last=self._chunk(chunk,fallback,scene_id,index)
                            if path is not None:
                                warnings.append(f"Cảnh {scene_id}, đoạn {index}: dùng giọng dự phòng {fallback} do TTS giọng {voice} lỗi.")
                        if path is None:
                            simple=clean_tts_text(chunk,simple=True)
                            path,last=self._chunk(simple,fallback,scene_id,index)
                            if path is not None: warnings.append(f"Cảnh {scene_id}, đoạn {index}: dùng văn bản rút gọn với giọng dự phòng.")
                        silent=path is None
                        if silent:
                            path=Path(work)/f"silent_{index}.mp3"
                            create_silence(path,planned*len(chunk)/sum(map(len,chunks)),self.settings.request_timeout_sec)
                            error=last
                            used=None
                            warnings.append(f"cảnh {scene_id} không có giọng đọc (đoạn {index}/{len(chunks)}): TTS lỗi; dùng im lặng và caption. Có thể chạy lại riêng audio cảnh {scene_id}.")
                        paths.append(path)
                        length=audio_duration(path)
                        from utils.word_timing import align_words
                        words,_=align_words(chunk,length,read_words(path.with_suffix(".words.json")))
                        timing_sources.append(timing_source(path.with_suffix(".words.json")))
                        boundaries.extend(dict(w,start=w["start"]+cursor,end=w["end"]+cursor) for w in words)
                        cursor+=length
                        parts.append({"index":index,"silent":silent,"voice":used,"error":last if silent else None})
                    self._join(paths,destination)
            metadata={"text_hash":cache_key(clean),"audio_silent":any(p["silent"] for p in parts),
                "audio_error":error,"voice_used":next((p["voice"] for p in parts if p["voice"]),None),
                "warnings":warnings,"chunks":parts}
            # Only successful speech chunks enter cache. Silence is always retryable.
            write_json_atomic(audio_metadata_path(destination),metadata)
            duration=audio_duration(destination)
            source=None if timing_sources and all(s=="word_boundary" for s in timing_sources) else "estimated_characters" if not timing_sources or all(s=="estimated_characters" for s in timing_sources) else "boundary_projected"
            save_words(destination.with_suffix(".words.json"),clean,duration,boundaries,source=source)
            return duration
