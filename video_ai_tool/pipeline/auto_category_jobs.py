"""Background category runs reuse pipeline worker infrastructure/cancellation."""
from pathlib import Path
from threading import Event
import uuid
from copy import deepcopy
from pipeline.run_all_jobs import PipelineJobs
from pipeline.auto_category import run_auto
from utils.diagnostics import Diagnostics

class AutoCategoryJobs(PipelineJobs):
    def submit_auto(self,params,settings,*,resume=None):
        with self.lock:
            active=next((key for key,v in self.jobs.items() if v["status"] in {"queued","running"}),None)
            if active: return active
            key=uuid.uuid4().hex
            self.jobs[key]={"status":"queued","project":str(Path(resume).resolve()) if resume else None,
                "state":None,"message":"Đang chờ","error":None,"traceback":None}
            self.cancel_events[key]=Event()
        self.executor.submit(self._auto_run,key,dict(params),settings,resume)
        return key
    def _auto_run(self,key,params,settings,resume):
        diagnostics=Diagnostics(settings.logs_dir,filename="auto_category_errors.log",secrets=[settings.gemini_api_key.get_secret_value(),settings.gateway_api_key.get_secret_value(),settings.youtube_api_key.get_secret_value(),settings.pexels_api_key.get_secret_value(),settings.pixabay_api_key.get_secret_value()])
        def progress(event):
            with self.lock:
                self.jobs[key].update(status="running",project=event["project"],state=deepcopy(event["state"]),message=event["message"])
        try:
            project=run_auto(**params,settings=settings,resume=resume,progress_cb=progress,cancel_event=self.cancel_events[key])
            from pipeline.projects import read_json
            with self.lock: self.jobs[key].update(status="finished",project=str(project),state=read_json(project/"run_state.json"))
        except Exception as error:
            diagnostics.record_exception(error,"Worker danh mục tự động")
            with self.lock: self.jobs[key].update(status="failed",error=diagnostics.redact(str(error)),traceback=diagnostics.format_exception(error))
