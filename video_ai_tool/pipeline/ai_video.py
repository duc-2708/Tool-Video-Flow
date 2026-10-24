"""Durable paid jobs; one bounded retry for confirmed generation_failed only."""
from utils.atomic_io import discard_temp_file, replace_file_retry, write_text_atomic, write_json_atomic, read_json_atomic
import argparse
import json
from pathlib import Path
import time
import re
from agents.video_prompt_writer import fallback_prompt,sanitize_video_prompt

from config.settings import get_settings
from editor.timeline import confined
from providers.video_gateway import VideoGateway,VideoRequest,GatewayVideoError,AmbiguousSubmission,GenerationFailed,MODELS
from utils.cache import cache_key
from utils.console import configure_console
from utils.diagnostics import Diagnostics
from utils.file_lock import file_lock
from utils.media import video_info


def diagnostics_for(settings):
    return Diagnostics(settings.logs_dir,filename="gateway_video_errors.log",secrets=[settings.gateway_api_key.get_secret_value()])


def load_job(path):
    path = Path(path).resolve()
    if path.parent.name != "ai_video" or path.suffix != ".json":
        raise ValueError("Job phải là file .json trong output/<project>/ai_video/.")
    data = read_json_atomic(path)
    VideoRequest.model_validate(data["request"])
    return data


def save_job(path,data,diagnostics):
    # Never persist HTTP authorization headers; failure payloads are redacted.
    write_json_atomic(path,json.loads(diagnostics.redact(json.dumps(data,ensure_ascii=False))))


def log_exception(diagnostics,error,context):
    try:
        diagnostics.record_exception(error,context)
    except OSError:
        pass  # Keep the recovery ID in the original error even if logs are locked.


def persist_remote_id(path, job, remote_id, diagnostics):
    """Never poll/process metadata before durably recording a known paid ID."""
    if not isinstance(remote_id,str) or not remote_id.strip():
        raise AmbiguousSubmission("Job chưa có remote ID. Kiểm tra dashboard; không tự gửi lại yêu cầu có phí.")
    job.update(remote_id=remote_id.strip(),status="queued",error=None)
    for attempt in range(3):
        try:
            save_job(path,job,diagnostics)
            return
        except OSError as error:
            log_exception(diagnostics,error,diagnostics.redact(
                f"Lưu remote ID thất bại lần {attempt+1}/3; remote_id={remote_id}. Không gửi lại POST."))
            if attempt < 2:
                time.sleep(.1 * (attempt+1))
    raise GatewayVideoError(diagnostics.redact(
        f"Gateway đã tạo job, remote ID: {remote_id}, nhưng không lưu được sau 3 lần. "
        "Dùng ID này để tiếp tục job có sẵn; không tạo lại vì có thể tính phí thêm."))


def suggest_after_timeout(path,job,error,diagnostics):
    if not (isinstance(error,TimeoutError) or re.search(r"timeout|timed[ _-]?out|hết thời gian|quá thời gian",str(error),re.I)):
        return
    job["simpler_prompt_suggestion"] = fallback_prompt(job.get("request",{}).get("prompt",""),simpler=True)
    job["retry_notice"] = "Đề xuất prompt đơn giản cho job MỚI; không tự gửi lại. Kiểm tra dashboard và xác nhận chi phí trước khi tạo."
    try:
        save_job(path,job,diagnostics)
    except OSError as save_error:
        log_exception(diagnostics,save_error,"Không lưu được đề xuất prompt sau timeout")


def create_job(project,request,settings,*,gateway=None,recreate_confirmed=False,retry_of=None):
    project = Path(project).resolve()
    if not project.is_dir():
        raise ValueError("Project chưa tồn tại. Tạo hoặc chọn project trước.")
    folder = confined(project,"ai_video")
    folder.mkdir(exist_ok=True)
    request = request.model_copy(update={"prompt":sanitize_video_prompt(request.prompt)})
    identity = request.model_dump(mode="json")
    if retry_of:
        identity = {"request":identity, "generation_retry_of":str(retry_of)}
    path = confined(folder,cache_key(identity)+".json")
    diagnostics = diagnostics_for(settings)
    client = gateway or VideoGateway(settings,diagnostics)
    try:
        with file_lock(confined(folder,"submit.lock")):
            history = []
            if path.exists():
                existing = load_job(path)
                if recreate_confirmed:
                    if existing.get("remote_id"):
                        raise GatewayVideoError("Job đã có remote ID; hãy tiếp tục job có sẵn, không tạo lại.")
                    if existing.get("clip_path"):
                        raise GatewayVideoError("Job đã có clip trên máy; không tạo lại.")
                    history = existing.get("previous_attempts",[])+[{key:value for key,value in existing.items() if key != "previous_attempts"}]
                    diagnostics.record("Người dùng xác nhận đã kiểm tra dashboard không có job và yêu cầu tạo lại. Có thể phát sinh thêm chi phí; không hoàn tiền/hủy job cũ.")
                elif existing["status"] in {"submitting","ambiguous"}:
                    raise AmbiguousSubmission("Yêu cầu này có lần gửi chưa rõ kết quả. Kiểm tra dashboard và dùng resume --remote-id ID; không tạo thêm job.")
                else:
                    return path
            job = {"request":request.model_dump(mode="json"),"remote_id":None,"status":"submitting", "progress":0,
                   "estimated_cost_vnd":request.estimated_cost_vnd,"actual_cost_vnd":None,"clip_path":None,"error":None}
            if retry_of:
                job["generation_retry_of"] = str(retry_of)
            if history:
                job.update(previous_attempts=history,recreate_confirmed=True,
                    cost_warning="Người dùng xác nhận dashboard không có job; lần gửi lại có thể phát sinh thêm chi phí.")
            from pipeline.ai_budget import reserve
            reserve(settings,str(path)+f':attempt:{len(history)}')
            save_job(path,job,diagnostics)
            try:
                diagnostics.record(json.dumps({"event":"submit_request", "request":request.payload(), "remote_id":None},ensure_ascii=False))
                response,cost = client.create(request)
                persist_remote_id(path,job,response.get("id"),diagnostics)
                diagnostics.record(json.dumps({"event":"submit_response", "request":request.payload(), "remote_id":job["remote_id"], "response":response},ensure_ascii=False,default=str))
                job.update(status=response.get("status","queued"),actual_cost_vnd=cost)
            except AmbiguousSubmission as error:
                job.update(status="ambiguous",error=diagnostics.redact(str(error)))
                suggest_after_timeout(path,job,error,diagnostics)
                save_job(path,job,diagnostics)
                raise
            except Exception as error:
                # Any interruption after POST might hide a successful paid job.
                # Known 4xx are recorded as rejected, never silently retried.
                job.update(status="queued" if job.get("remote_id") else "rejected" if isinstance(error,GatewayVideoError) else "ambiguous",error=diagnostics.redact(str(error)))
                suggest_after_timeout(path,job,error,diagnostics)
                try:
                    save_job(path,job,diagnostics)
                except OSError as save_error:
                    log_exception(diagnostics,save_error,"Không lưu được lỗi gửi job; giữ nguyên lỗi chứa remote ID để khôi phục")
                raise
            save_job(path,job,diagnostics)
        return path
    except Exception as error:
        log_exception(diagnostics,error,"Tạo job AI Video")
        raise
    finally:
        if gateway is None:
            client.close()


def recreate_job(path,settings,*,confirmed=False,gateway=None):
    if not confirmed:
        raise GatewayVideoError("Cần xác nhận đã kiểm tra dashboard không có job. Tạo lại có thể phát sinh chi phí.")
    path = Path(path).resolve()
    # Serialize with GET recovery; create_job also serializes all paid submits.
    job = load_job(path)
    request = VideoRequest.model_validate(job["request"])
    if path.stem != cache_key(request.model_dump(mode="json")):
        raise ValueError("Đường dẫn job không khớp yêu cầu đã lưu.")
    with file_lock(confined(path.parent,path.stem+".lock")):
        return create_job(path.parent.parent,request,settings,gateway=gateway,recreate_confirmed=True)


def _resume_job_once(path,settings,*,remote_id=None,progress=None,gateway=None,wait_sec=1800,poll_sec=5):
    path = Path(path).resolve()
    job = load_job(path)
    project = path.parent.parent
    diagnostics = diagnostics_for(settings)
    notify = progress or (lambda value,message:None)
    client = gateway or VideoGateway(settings,diagnostics)
    try:
        # Separate lock from submission so it is safe to resume after a restart.
        with file_lock(confined(path.parent,path.stem+".lock")):
            job = load_job(path)
            if remote_id:
                if job.get("remote_id") and job["remote_id"] != remote_id:
                    raise ValueError("Job đã có ID khác; không thay ID đã lưu.")
                persist_remote_id(path,job,remote_id,diagnostics)
            if not job.get("remote_id"):
                raise GatewayVideoError("Job chưa có remote ID. Kiểm tra dashboard gateway; dùng resume --remote-id ID để tiếp tục mà không tạo mới.")
            request = VideoRequest.model_validate(job["request"])
            if job.get("clip_path"):
                existing = confined(project,job["clip_path"])
                if existing.is_file():
                    notify(1.,"Clip đã có trên máy; không tạo lại")
                    return job
            deadline = time.monotonic()+wait_sec
            while True:
                if time.monotonic() >= deadline:
                    raise TimeoutError("Hết thời gian chờ; job đã lưu. Bấm Tiếp tục hoặc dùng lệnh resume, không cần tạo lại.")
                status = client.status(job["remote_id"],request.model)
                state = str(status.get("status","unknown"))
                try:
                    percent = min(100,max(0,float(status.get("progress") or 0)))
                except (TypeError,ValueError):
                    percent = 0
                job.update(status=state,progress=percent,error=None)
                if state in {"failed","error","cancelled","canceled","generation_failed"}:
                    job["error"] = diagnostics.redact(str(status.get("error") or "Gateway báo tạo video thất bại."))
                    job["gateway_failure"] = json.loads(diagnostics.redact(json.dumps(status,ensure_ascii=False,default=str)))
                    job["sent_payload"] = request.payload()
                    generation_failed = state == "generation_failed" or contains_generation_failed(status.get("error")) or status.get("code") == "generation_failed"
                    job["failure_code"] = "generation_failed" if generation_failed else "gateway_failed"
                    diagnostics.record(json.dumps({"event":"generation_error", "remote_id":job["remote_id"],
                        "request":request.payload(), "response":status},ensure_ascii=False,default=str))
                    save_job(path,job,diagnostics)
                    if generation_failed:
                        raise GenerationFailed("generation_failed: " + job["error"])
                    raise GatewayVideoError(job["error"])
                save_job(path,job,diagnostics)
                notify(.05+.80*percent/100,f"{request.model}: {state} · {percent:.0f}%")
                if state == "completed":
                    break
                time.sleep(poll_sec)
            notify(.9,"Đang tải và kiểm tra MP4")
            clips = confined(project,"clips")
            clips.mkdir(exist_ok=True)
            destination = confined(clips,f"ai_{path.stem}.mp4")
            temporary = confined(clips,f".ai_{path.stem}.part")
            response = None
            try:
                response = client.download(job["remote_id"],request.model)
                media_type = response.headers.get("Content-Type","").split(";")[0].lower()
                if media_type not in {"video/mp4","application/octet-stream"}:
                    raise GatewayVideoError("Endpoint tải clip không trả MP4/binary hợp lệ.")
                size = 0
                with temporary.open("wb") as stream:
                    for chunk in response.iter_content(256*1024):
                        if not chunk:
                            continue
                        size += len(chunk)
                        if size > 512*1024**2 or time.monotonic() >= deadline:
                            raise GatewayVideoError("Tải clip vượt dung lượng 512 MB hoặc hết thời gian chờ; có thể resume.")
                        stream.write(chunk)
                width,height,duration = video_info(temporary)
                replace_file_retry(temporary, destination)
            finally:
                if response is not None:
                    response.close()
                discard_temp_file(temporary)
            job.update(status="completed",progress=100,clip_path=destination.relative_to(project).as_posix(),
                width=width,height=height,duration_sec=duration,size_bytes=destination.stat().st_size,error=None)
            save_job(path,job,diagnostics)
            credits = confined(path.parent,path.stem+".credits.txt")
            write_text_atomic(credits, f"AI-generated clip\nGateway: https://api.buihuuthang.com\nModel: {request.model}\nJob: {job['remote_id']}\nFile: {destination.name}\n")
            notify(1.,"Clip AI đã tải xong")
            return job
    except Exception as error:
        suggest_after_timeout(path,job,error,diagnostics)
        diagnostics.record_exception(error,"Tiếp tục job AI Video")
        raise
    finally:
        if gateway is None:
            client.close()


def contains_generation_failed(value):
    if isinstance(value, dict):
        return any(contains_generation_failed(item) for item in value.values())
    if isinstance(value, list):
        return any(contains_generation_failed(item) for item in value)
    return isinstance(value, str) and "generation_failed" in value.lower()


def resume_job(path,settings,*,remote_id=None,progress=None,gateway=None,wait_sec=1800,poll_sec=5):
    """One durable retry ONLY for a confirmed generation_failed; never timeout/403."""
    path = Path(path).resolve()
    kwargs = dict(progress=progress,gateway=gateway,wait_sec=wait_sec,poll_sec=poll_sec)
    try:
        return _resume_job_once(path,settings,remote_id=remote_id,**kwargs)
    except GenerationFailed:
        diagnostics = diagnostics_for(settings)
        with file_lock(confined(path.parent,path.stem+".retry.lock")):
            root = load_job(path)
            if root.get("generation_retry_of"):
                raise GenerationFailed("generation_failed: đã hết một lần thử lại; dùng b-roll thường, không tạo thêm job.")
            relative = root.get("generation_retry_path")
            if relative:
                retry_path = confined(path.parent,relative)
                if not retry_path.exists():
                    raise AmbiguousSubmission("Lần thử lại đã được ghi nhận nhưng chưa có file job; kiểm tra dashboard, không tự gửi thêm.")
            else:
                request = VideoRequest.model_validate(root["request"])
                request = request.model_copy(update={"prompt":sanitize_video_prompt(request.prompt,simpler=True)})
                identity = {"request":request.model_dump(mode="json"),"generation_retry_of":path.stem}
                retry_path = confined(path.parent,cache_key(identity)+".json")
                root.update(generation_retry_path=retry_path.name,generation_retry_count=1,
                    retry_notice="Tự thử lại tối đa 1 job có thể tính phí sau generation_failed; không retry timeout hoặc thiếu ID.")
                save_job(path,root,diagnostics)  # Intent BEFORE any second paid POST.
                if progress:
                    progress(.01,"generation_failed: thử lại một lần bằng prompt dự phòng an toàn (có thể tính phí)")
                retry_path = create_job(path.parent.parent,request,settings,gateway=gateway,retry_of=path.stem)
            try:
                result = _resume_job_once(retry_path,settings,**kwargs)
                result = {**result,"effective_job_path":str(retry_path)}
                root.update(generation_retry_completed=True,error=None)
                save_job(path,root,diagnostics)
                return result
            except Exception as error:
                root.update(generation_retry_exhausted=True,error=diagnostics.redact(
                    f"Thử lại Clip AI không thành công: {error}. Dùng b-roll thường; không tạo thêm job."))
                save_job(path,root,diagnostics)
                log_exception(diagnostics,error,"Clip AI đã dùng hết một lần thử lại")
                raise GatewayVideoError(root["error"]) from error


def main():
    configure_console()
    parser = argparse.ArgumentParser(description="Veo/Seedance qua gateway; generation_failed có tối đa 1 job thử lại có phí; timeout/thiếu ID không tự gửi lại.")
    actions = parser.add_subparsers(dest="action",required=True)
    actions.add_parser("models")
    create = actions.add_parser("create")
    create.add_argument("--project",type=Path,required=True)
    create.add_argument("--prompt",required=True)
    create.add_argument("--model",choices=list(MODELS))
    create.add_argument("--seconds",type=int)
    create.add_argument("--format",choices=["tiktok","youtube"],default="tiktok")
    create.add_argument("--resolution",choices=["720p","1080p"],default="720p")
    create.add_argument("--yes",action="store_true",help="Xác nhận tạo clip và tối đa một job thử lại có thể tính phí khi generation_failed")
    resume = actions.add_parser("resume")
    resume.add_argument("job",type=Path)
    resume.add_argument("--remote-id")
    recreate = actions.add_parser("recreate")
    recreate.add_argument("job",type=Path)
    recreate.add_argument("--confirm-no-job",action="store_true")
    recreate.add_argument("--yes",action="store_true")
    args = parser.parse_args()
    diagnostics = None
    try:
        settings = get_settings()
        diagnostics = diagnostics_for(settings)
        if args.action == "models":
            client = VideoGateway(settings,diagnostics)
            try:
                for model in client.models():
                    print(model["id"])
            finally:
                client.close()
            return
        if args.action == "create":
            model = args.model or settings.gateway_video_model
            seconds = args.seconds if args.seconds is not None else settings.ai_clip_seconds if model == settings.gateway_video_model else MODELS[model][0]
            request = VideoRequest(model=model,prompt=args.prompt,seconds=seconds,format=args.format,resolution=args.resolution)
            if not args.yes:
                print(f"Chi phí tham khảo: {request.estimated_cost_vnd:,} VNĐ/job; generation_failed được thử thêm tối đa 1 job có thể tính phí. Thêm --yes để gửi tạo video.")
                return
            job_path = create_job(args.project,request,settings)
        elif args.action == "recreate":
            job_path = recreate_job(args.job,settings,confirmed=args.confirm_no_job and args.yes)
        else:
            job_path = args.job
        print(f"Job đã lưu: {job_path}")
        result = resume_job(job_path,settings,remote_id=getattr(args,"remote_id",None),progress=lambda value,message:print(message,flush=True))
        print("Đã tải: "+result["clip_path"])
    except Exception as error:
        if diagnostics:
            diagnostics.record_exception(error,"CLI AI Video")
            print(diagnostics.redact(str(error)))
        else:
            print("Cấu hình không hợp lệ. Kiểm tra kiểu/giá trị theo .env.example.")
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
