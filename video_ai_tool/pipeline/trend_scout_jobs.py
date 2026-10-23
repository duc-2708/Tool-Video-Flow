"""Reuse discovery's bounded worker and snapshot lifecycle for Trend Scout."""
from pipeline.discovery_jobs import DiscoveryJobs
from pipeline.trend_scout import scout
from utils.diagnostics import Diagnostics


class TrendScoutJobs(DiscoveryJobs):
    def _run(self, key, settings, kwargs):
        try:
            result = scout(settings=settings, **kwargs)
            with self.lock:
                self.jobs[key].update(status="done", result=result)
        except Exception as error:
            diagnostics = Diagnostics(settings.logs_dir, filename="trend_scout_errors.log")
            diagnostics.record_exception(error, "Worker Trend Scout")
            with self.lock:
                self.jobs[key].update(status="failed", error=diagnostics.redact(str(error)))
