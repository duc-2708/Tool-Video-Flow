"""Background analysis keeps Streamlit navigation responsive."""
from pipeline.run_all_jobs import PipelineJobs
from pipeline.style_learner import analyze_batch, style_diagnostics
from uuid import uuid4


class StyleJobs(PipelineJobs):
    def submit_analysis(self, filenames, settings):
        with self.lock:
            active = next((k for k, v in self.jobs.items() if v["status"] in {"queued", "running"}), None)
            if active:
                return active
            key = uuid4().hex
            self.jobs[key] = {"status": "queued", "message": "Đang chờ", "results": [], "error": None}
        self.executor.submit(self._analyze, key, list(filenames), settings)
        return key

    def _analyze(self, key, filenames, settings):
        diagnostics = style_diagnostics(settings)

        def progress(message):
            with self.lock:
                self.jobs[key].update(status="running", message=diagnostics.redact(message))

        try:
            results = analyze_batch(settings, filenames, progress=progress)
            with self.lock:
                self.jobs[key].update(status="finished", results=results, message="Đã xử lý xong lô video.")
        except Exception as error:
            diagnostics.record_exception(error, "Style worker")
            with self.lock:
                self.jobs[key].update(status="failed", error=diagnostics.redact(str(error)))
