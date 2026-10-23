"""Shared rolling-minute reservations for Style Gemini, including HTTP retries."""
import math
import time
from utils.atomic_io import read_json_atomic,write_json_atomic
from utils.file_lock import file_lock


def estimated_video_tokens(settings,duration,prompt_chars=0):
    # Conservative planning values: frame tokens + audio/metadata. Not billing.
    frame=64 if settings.style_media_resolution=="low" else 256
    return math.ceil(duration*(frame*settings.style_video_fps+40)+prompt_chars/3)


def reserve_style_request(settings,tokens,progress=lambda message:None,*,clock=None,sleep=None):
    clock=clock or time.time;sleep=sleep or time.sleep
    tokens=max(1,int(tokens))
    if tokens>settings.style_tpm_limit:
        raise ValueError(f"Một video ước lượng {tokens:,} token vượt STYLE_TPM_LIMIT={settings.style_tpm_limit:,}; giảm STYLE_VIDEO_FPS, chọn low hoặc cắt video trước khi học.")
    path=settings.cache_dir/"style_rate_limit.json"
    while True:
        with file_lock(path.with_suffix(".lock")):
            now=clock()
            data=read_json_atomic(path) if path.exists() else {"requests":[]}
            requests=data.get("requests")
            if not isinstance(requests,list) or any(not isinstance(r,dict) or type(r.get("at")) not in (int,float) or type(r.get("tokens")) is not int or r["tokens"]<1 for r in requests):
                raise ValueError("Ledger giới hạn Style không hợp lệ; chưa gửi Gemini.")
            requests=[r for r in requests if r["at"]>now-60]
            delay=0.
            if requests:
                delay=max(0.,max(r["at"] for r in requests)+settings.style_request_interval_sec-now)
            if len(requests)>=settings.style_rpm_limit or sum(r["tokens"] for r in requests)+tokens>settings.style_tpm_limit:
                delay=max(delay,min(r["at"] for r in requests)+60-now+.01)
            if delay<=0:
                requests.append({"at":now,"tokens":tokens})
                write_json_atomic(path,{"requests":requests})
                return
        progress(f"Đang chờ giới hạn Gemini Style ({delay:.1f}s); RPM={settings.style_rpm_limit}, TPM={settings.style_tpm_limit:,}.")
        sleep(min(5.,delay))
