"""Optional deterministic Chromium -> FFmpeg scene cache; never edits Render inputs."""
from contextlib import contextmanager
import base64
import hashlib
import io
import json
import math
from pathlib import Path
import subprocess
from tempfile import TemporaryFile
import time
from functools import lru_cache
from uuid import uuid4

from imageio_ffmpeg import get_ffmpeg_exe
from PIL import Image
import numpy as np
from utils.atomic_io import discard_temp_file,replace_file_retry,write_json_atomic
from utils.cache import cache_key
from utils.file_lock import file_lock
from utils.word_timing import align_words,read_words,timing_source

MOTION_DIR=Path(__file__).resolve().parents[1]/"editor/motion"
SUPPORTED={"hook_card","steps_list","compare_bars"}


@lru_cache(maxsize=4)
def background_images(size):
    """Pre-rasterize gradients: Chromium CSS-gradient dithering varies by paint."""
    width,height=size
    y,x=np.mgrid[0:height,0:width]
    mix=(y/height)[...,None]
    base=np.array([16,27,48])*(1-mix)+np.array([8,12,23])*mix
    base=np.broadcast_to(base,(height,width,3)).copy()
    glow=np.maximum(0,1-np.sqrt(((x-width*.15)/width)**2+((y-height*.18)/height)**2)/.8)[...,None]
    base+=glow*np.array([5,14,17])
    radius=np.sqrt(((x:=np.arange(180)[None,:])-90)**2+((y:=np.arange(180)[:,None])-90)**2)
    orb=np.zeros((180,180,4),dtype=np.uint8);orb[:,:,:3]=[138,213,223];orb[:,:,3]=np.maximum(0,1-radius/90)**2*36
    def uri(pixels):
        buffer=io.BytesIO();Image.fromarray(pixels).save(buffer,format="PNG")
        return "data:image/png;base64,"+base64.b64encode(buffer.getvalue()).decode("ascii")
    return uri(np.clip(base,0,255).astype(np.uint8)),uri(orb)


def scene_payload(scene,size,caption_style):
    words,method=align_words(scene.spec.narration,scene.duration,read_words(scene.audio.with_suffix(".words.json")))
    origin=timing_source(scene.audio.with_suffix(".words.json"))
    return {"width":size[0],"height":size[1],"duration":scene.duration,"words":words,"timing_source":origin if origin!="word_boundary" else method,
        "captions":caption_style.model_dump(mode="json"),"shots":[{
            "start":s.start-scene.start,"duration":s.duration,
            "template":s.spec.visual.template if s.spec.visual else "stock",
            "data":s.spec.visual.data.model_dump(mode="json") if s.spec.visual else {},
            "beats":[b.model_dump(mode="json") for b in s.spec.visual.beats] if s.spec.visual else []
        } for s in scene.shots]}


def html_document(payload,font):
    # Embed a single local font: no HTTP/file-origin font access, no remote resources.
    encoded=base64.b64encode(Path(font).read_bytes()).decode("ascii")
    css=(MOTION_DIR/"base.css").read_text(encoding="utf-8").replace("__FONT__","data:font/otf;base64,"+encoded)
    bg,orb=background_images((payload["width"],payload["height"]))
    css+=f'#stage{{background-image:url("{bg}");background-size:100% 100%}}.orb{{background-image:url("{orb}");background-size:100% 100%}}.bar-fill{{background:var(--accent)}}'
    data=json.dumps(payload,ensure_ascii=True).replace("<","\\u003c").replace(">","\\u003e").replace("&","\\u0026")
    js=(MOTION_DIR/"runtime.js").read_text(encoding="utf-8")
    return '<!doctype html><meta charset="utf-8"><style>'+css+'</style><div id="stage"></div><script>window.MOTION_DATA='+data+';</script><script>'+js+'</script>'


@contextmanager
def browser_page(size):
    """Imported only on a motion cache miss. Missing package/browser is recoverable."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as runtime:
        browser=runtime.chromium.launch(headless=True,timeout=20000,
            args=["--disable-gpu","--disable-lcd-text","--force-color-profile=srgb"])
        try:
            context=browser.new_context(viewport={"width":size[0],"height":size[1]},device_scale_factor=1,
                locale="vi-VN",color_scheme="dark",reduced_motion="reduce",service_workers="block")
            context.route("**/*",lambda route:route.abort())
            page=context.new_page()
            page.set_default_timeout(15000)
            yield page
        finally:
            browser.close()


def capture(page,payload,font,*,png=False):
    page.set_content(html_document(payload,font),wait_until="load")
    page.evaluate("() => document.fonts.ready")
    page.evaluate("() => window.renderAt(0)")


def render_scene(scene,cache_dir,*,size,font,caption_style,fps=30,static_frame=None,
                 progress=None,diagnostics=None,extra_identity=None):
    """Return cache result or None on engine failure; caller retains Pillow path.

    Unsupported templates are rendered by the existing frame callback, not by an
    imitation HTML template. Beat seconds/word indexes are scene-local/zero-based.
    """
    payload=scene_payload(scene,size,caption_style)
    if not any(s["template"] in SUPPORTED for s in payload["shots"]): return None
    sources=[]
    for shot in scene.shots:
        path=shot.path
        sources.append((str(path),path.stat().st_size,path.stat().st_mtime_ns) if path and path.is_file() else None)
    identity={"payload":payload,"fps":fps,"sources":sources,"extra":extra_identity,
        "engine":hashlib.sha256(Path(__file__).read_bytes()+(MOTION_DIR/"runtime.js").read_bytes()+(MOTION_DIR/"base.css").read_bytes()+Path(font).read_bytes()).hexdigest()}
    key=cache_key(identity);folder=Path(cache_dir);destination=folder/(key+".mp4");meta=folder/(key+".json")
    started=time.perf_counter();notify=progress or (lambda value,message:None)
    temporary=None;process=None
    try:
        folder.mkdir(parents=True,exist_ok=True)
        with file_lock(folder/(key+".lock"),timeout=180):
            started=time.perf_counter()
            if destination.is_file() and meta.is_file():
                record=json.loads(meta.read_text(encoding="utf-8"))
                if destination.stat().st_size==record.get("size_bytes") and record.get("sha256")==hashlib.sha256(destination.read_bytes()).hexdigest():
                    notify(1.,f"Motion cảnh {scene.spec.id}: dùng cache")
                    return dict(record,path=str(destination),cache_hit=True,render_seconds=0.)
            temporary=folder/(uuid4().hex+".tmp.mp4")
            count=max(1,math.ceil(scene.duration*fps));last=0.
            with browser_page(size) as page, TemporaryFile() as errors:
                capture(page,payload,font)
                process=subprocess.Popen([get_ffmpeg_exe(),"-hide_banner","-loglevel","error","-y",
                    "-f","image2pipe","-vcodec","mjpeg","-framerate",str(fps),"-i","pipe:0","-an",
                    "-c:v","libx264","-preset","veryfast","-crf","20","-pix_fmt","yuv420p","-movflags","+faststart",str(temporary)],
                    stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=errors)
                try:
                    for i in range(count):
                        t=min(i/fps,scene.duration-1e-6)
                        shot=next((s for s in payload["shots"] if s["start"]<=t<s["start"]+s["duration"]),payload["shots"][-1])
                        if shot["template"] in SUPPORTED:
                            page.evaluate("t => window.renderAt(t)",t)
                            frame=page.screenshot(type="jpeg",quality=92,animations="disabled",caret="hide",timeout=15000)
                        elif static_frame:
                            buf=io.BytesIO();Image.fromarray(static_frame(t)).save(buf,format="JPEG",quality=92);frame=buf.getvalue()
                        else:
                            # Standalone demos can supply all shots with supported templates.
                            raise ValueError("Thiếu callback renderer tĩnh cho mẫu không hỗ trợ motion.")
                        process.stdin.write(frame)
                        now=time.perf_counter()
                        if now-last>.5 or i==count-1:
                            elapsed=now-started;remaining=elapsed/(i+1)*(count-i-1)
                            notify((i+1)/count,f"Motion cảnh {scene.spec.id}: {i+1}/{count} khung · còn khoảng {remaining:.0f}s")
                            last=now
                    process.stdin.close()
                    code=process.wait(timeout=90)
                    if code:
                        errors.seek(0);raise RuntimeError("FFmpeg motion: "+errors.read().decode("utf-8",errors="replace")[:2000])
                finally:
                    if process.poll() is None: process.kill();process.wait(timeout=15)
            replace_file_retry(temporary,destination)
            result={"path":str(destination),"cache_hit":False,"scene_id":scene.spec.id,"width":size[0],"height":size[1],
                "fps":fps,"duration_sec":scene.duration,"render_seconds":round(time.perf_counter()-started,3),
                "size_bytes":destination.stat().st_size,"sha256":hashlib.sha256(destination.read_bytes()).hexdigest(),"timing_source":payload["timing_source"]}
            write_json_atomic(meta,result)
            return result
    except Exception as error:
        if diagnostics: diagnostics.record_exception(error,f"Motion cảnh {scene.spec.id}: dùng renderer Pillow dự phòng")
        notify(1.,f"Motion cảnh {scene.spec.id} chưa dùng được; chuyển đồ họa Pillow hiện có")
        return None
    finally:
        if temporary: discard_temp_file(temporary)
