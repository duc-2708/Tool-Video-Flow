"""Background AI video workers; durable state lives in project/ai_video/."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path
from threading import Lock
import uuid
from pipeline.ai_video import create_job,recreate_job,resume_job,diagnostics_for


class AIVideoJobs:
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=1,thread_name_prefix="gateway-video")
        self.lock = Lock()
        self.jobs = {}

    def active(self,project):
        with self.lock:
            return next((key for key,value in self.jobs.items() if value["project"] == str(Path(project).resolve()) and value["status"] in {"queued","running"}),None)

    def snapshot(self,key):
        with self.lock:
            return deepcopy(self.jobs.get(key))

    def submit(self,project,request,settings,*,job_path=None,remote_id=None,recreate_confirmed=False):
        project = Path(project).resolve()
        with self.lock:
            active = next((key for key,value in self.jobs.items() if value["project"] == str(project) and value["status"] in {"queued","running"}),None)
            if active:
                return active
            key = uuid.uuid4().hex
            self.jobs[key] = {"project":str(project),"status":"queued","progress":0.,"message":"Đang chờ","job_path":None,"error":None,"traceback":None}
        self.executor.submit(self._run,key,project,request,settings,job_path,remote_id,recreate_confirmed)
        return key

    def _run(self,key,project,request,settings,path,remote_id,recreate_confirmed=False):
        diagnostics = diagnostics_for(settings)
        def progress(value,message):
            with self.lock:
                current = self.jobs[key]
                current.update(status="running",progress=max(current["progress"],value),message=message)
        try:
            if recreate_confirmed:
                path = recreate_job(path,settings,confirmed=True)
            elif path is None:
                progress(.01,"Đang gửi yêu cầu tạo clip có tính phí")
                path = create_job(project,request,settings)
            with self.lock:
                self.jobs[key]["job_path"] = str(path)
            result = resume_job(path,settings,progress=progress,remote_id=remote_id)
            with self.lock:
                self.jobs[key].update(status="completed",progress=1.,message="Clip đã sẵn sàng",result=result)
        except Exception as error:
            diagnostics.record_exception(error,"Worker AI Video")
            with self.lock:
                self.jobs[key].update(status="failed",error=diagnostics.redact(str(error)),traceback=diagnostics.format_exception(error))
