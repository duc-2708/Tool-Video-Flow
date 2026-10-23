"""Use the existing background job infrastructure for metadata and approved learning."""
from uuid import uuid4
from pipeline.run_all_jobs import PipelineJobs
from pipeline.scan_sources import preview_scan, learn_selected
from pipeline.style_learner import style_diagnostics


class ScanJobs(PipelineJobs):
    def submit_scan(self, settings, category, **options):
        return self._submit("scan",settings,category,options)

    def submit_learning(self, settings, category, rows):
        return self._submit("learn",settings,category,{"rows":rows,"confirmed":True})

    def _submit(self, kind, settings, category, options):
        with self.lock:
            active=next((k for k,v in self.jobs.items() if v["status"] in {"queued","running"}),None)
            if active:
                return active
            key=uuid4().hex
            self.jobs[key]={"status":"queued","kind":kind,"category":category,"message":"Đang chờ","result":None,"error":None}
        self.executor.submit(self._run_scan,key,settings,category,options)
        return key

    def _run_scan(self, key, settings, category, options):
        diagnostics=style_diagnostics(settings)
        def progress(message):
            with self.lock:
                self.jobs[key].update(status="running",message=diagnostics.redact(message))
        try:
            fn=preview_scan if self.jobs[key]["kind"]=="scan" else learn_selected
            result=fn(settings,category,progress=progress,**options)
            with self.lock:
                self.jobs[key].update(status="finished",result=result,message="Đã xử lý xong.")
        except Exception as error:
            diagnostics.record_exception(error,"Style scan worker")
            with self.lock:
                self.jobs[key].update(status="failed",error=diagnostics.redact(str(error)))
