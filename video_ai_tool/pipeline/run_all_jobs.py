"""Background orchestration and cooperative cancellation for Streamlit."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import Event,Lock
import uuid
from pathlib import Path
from pipeline.run_all import run_all
from utils.diagnostics import Diagnostics


class PipelineJobs:
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=1,thread_name_prefix="pipeline-all")
        self.lock = Lock()
        self.jobs = {}
        self.cancel_events = {}

    def snapshot(self,key):
        with self.lock:
            return deepcopy(self.jobs.get(key))

    def active(self,project=None):
        with self.lock:
            return next((key for key,value in self.jobs.items() if value["status"] in {"queued","running"}
                and (project is None or value.get("project") == str(Path(project).resolve()))),None)

    def cancel(self,key):
        with self.lock:
            if key in self.cancel_events:
                self.cancel_events[key].set()

    def submit(self,config,settings):
        with self.lock:
            # One pipeline at a time in this Streamlit process, even when a
            # second session clicks twice. Per-project file locks also cover CLI.
            active = next((key for key,value in self.jobs.items() if value["status"] in {"queued","running"}),None)
            if active:
                return active
            key = uuid.uuid4().hex
            self.jobs[key] = {"status":"queued","project":str(config.resume.resolve()) if config.resume and not config.force else None,
                "state":None,"message":"Đang chờ","error":None,"traceback":None}
            self.cancel_events[key] = Event()
        self.executor.submit(self._run,key,config,settings)
        return key

    def _run(self,key,config,settings):
        def progress(event):
            with self.lock:
                self.jobs[key].update(status="running",project=event["project"],message=event["message"],state=deepcopy(event["state"]))
        diagnostics = Diagnostics(settings.logs_dir,filename="run_all_errors.log",
            secrets=[settings.gateway_api_key.get_secret_value(),settings.gemini_api_key.get_secret_value()])
        try:
            project = run_all(config,progress,settings=settings,cancel_event=self.cancel_events[key])
            with self.lock:
                self.jobs[key].update(status="finished",project=str(project))
        except Exception as error:
            diagnostics.record_exception(error,"Pipeline worker")
            with self.lock:
                self.jobs[key].update(status="failed",error=diagnostics.redact(str(error)),traceback=diagnostics.format_exception(error))
