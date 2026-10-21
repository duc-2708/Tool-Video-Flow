"""Background discovery worker; no API calls on Streamlit page load."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import Lock
import uuid
from sources.topic_discovery import discover_topics
from utils.diagnostics import Diagnostics

class DiscoveryJobs:
    def __init__(self):
        self.pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix="topic-discovery")
        self.lock=Lock();self.jobs={}
    def snapshot(self,key):
        with self.lock: return deepcopy(self.jobs.get(key))
    def submit(self,settings,**kwargs):
        with self.lock:
            running=next((key for key,value in self.jobs.items() if value["status"]=="running"),None)
            if running: return running
            key=uuid.uuid4().hex;self.jobs[key]={"status":"running","result":None,"error":None}
        self.pool.submit(self._run,key,settings,kwargs)
        return key
    def _run(self,key,settings,kwargs):
        try:
            result=discover_topics(settings=settings,**kwargs)
            with self.lock: self.jobs[key].update(status="done",result=result)
        except Exception as error:
            diagnostics=Diagnostics(settings.logs_dir,filename="topic_discovery_errors.log")
            diagnostics.record_exception(error,"Worker khám phá")
            with self.lock: self.jobs[key].update(status="failed",error=diagnostics.redact(str(error)))
