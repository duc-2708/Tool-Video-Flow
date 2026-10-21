"""Thread-safe render jobs. Workers never call Streamlit APIs."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path
from threading import Lock
import uuid

from utils.diagnostics import Diagnostics


class RenderJobs:
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=1,thread_name_prefix="video-editor")
        self.lock = Lock()
        self.jobs = {}

    def snapshot(self,job_id):
        with self.lock:
            return deepcopy(self.jobs.get(job_id))

    def active(self,project):
        with self.lock:
            return next((key for key,value in self.jobs.items() if value["project"] == str(Path(project).resolve()) and value["status"] in {"queued","running"}),None)

    def submit(self,plan,mode,settings,secrets=()):
        project = str(Path(plan).resolve().parent)
        with self.lock:
            existing = next((key for key,value in self.jobs.items() if value["project"] == project and value["status"] in {"queued","running"}),None)
            if existing:
                return existing
            job_id = uuid.uuid4().hex
            self.jobs[job_id] = {"project":project,"mode":mode,"status":"queued","progress":0.,"message":"Đang chờ render","result":None,"error":None,"traceback":None}
        self.executor.submit(self._run,job_id,Path(plan),mode,settings,secrets)
        return job_id

    def _run(self,job_id,plan,mode,settings,secrets):
        diagnostics = Diagnostics(settings.logs_dir,filename="render_errors.log",secrets=list(secrets))
        def progress(value,message):
            with self.lock:
                job = self.jobs[job_id]
                job.update(status="running",progress=max(job["progress"],value),message=message)
        try:
            from editor.render import run_render
            result = run_render(plan,mode=mode,settings=settings,progress=progress,diagnostics=diagnostics)
            with self.lock:
                self.jobs[job_id].update(status="complete",progress=1.,message="Render hoàn tất",result=result)
        except Exception as error:
            diagnostics.record_exception(error,"Worker Render thất bại")
            with self.lock:
                self.jobs[job_id].update(status="failed",error=diagnostics.redact(str(error)),traceback=diagnostics.format_exception(error))
