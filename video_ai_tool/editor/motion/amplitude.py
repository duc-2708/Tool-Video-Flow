"""33ms RMS mouth envelope, cached under render/, never edits audio inputs."""
import hashlib,subprocess
import numpy as np
from imageio_ffmpeg import get_ffmpeg_exe
from utils.atomic_io import read_json_atomic,write_json_atomic


def envelope(audio,folder):
    folder.mkdir(parents=True,exist_ok=True)
    key=hashlib.sha256(audio.read_bytes()+b'rms33ms-v1').hexdigest()
    path=folder/(key+'.json')
    if path.exists(): return read_json_atomic(path)
    result=subprocess.run([get_ffmpeg_exe(),'-hide_banner','-loglevel','error','-i',str(audio),'-f','f32le','-ac','1','-ar','16000','pipe:1'],capture_output=True,timeout=90,check=True)
    pcm=np.frombuffer(result.stdout,dtype='<f4');step=528
    rms=[float(np.sqrt(np.mean(pcm[i:i+step]**2))) for i in range(0,len(pcm),step)]
    reference=max(.02,float(np.quantile(rms,.9))) if rms else 1.
    values=[round(min(1,max(0,(v-.003)/reference)),4) for v in rms]
    data={'audio_sha256':hashlib.sha256(audio.read_bytes()).hexdigest(),'interval_sec':.033,'values':values,'method':'RMS, not phoneme alignment'}
    write_json_atomic(path,data)
    return data
