"""Batch runner for producing multiple distinct videos automatically."""
import threading
import time
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Optional

from config.settings import get_settings
from pipeline.auto_category import run_auto
from pipeline.projects import read_json
from utils.diagnostics import Diagnostics


class BatchJobs:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance.lock = threading.Lock()
                cls._instance.status = "idle"  # idle, running, cancelled, done
                cls._instance.current_index = 0
                cls._instance.total_count = 0
                cls._instance.created_projects = []
                cls._instance.current_job_key = None
                cls._instance.log = []
                cls._instance.cancel_event = threading.Event()
                cls._instance.thread = None
        return cls._instance

    def is_running(self) -> bool:
        with self.lock:
            return self.status == "running"

    def snapshot(self) -> Dict[str, Any]:
        with self.lock:
            return {
                "status": self.status,
                "current_index": self.current_index,
                "total_count": self.total_count,
                "created_projects": list(self.created_projects),
                "log": list(self.log[-25:]),
            }

    def cancel(self):
        with self.lock:
            if self.status == "running":
                self.cancel_event.set()
                self.status = "cancelled"
                self.log.append("⚠️ Người dùng đã yêu cầu dừng chạy loạt!")

    def start_batch(self, params: Dict[str, Any], count: int, settings=None):
        with self.lock:
            if self.status == "running":
                return False
            self.status = "running"
            self.current_index = 0
            self.total_count = count
            self.created_projects = []
            self.log = [f"🚀 Bắt đầu tạo tự động loạt {count} video..."]
            self.cancel_event.clear()

        settings = settings or get_settings()
        self.thread = threading.Thread(
            target=self._run_loop,
            args=(params, count, settings),
            daemon=True
        )
        self.thread.start()
        return True

    def _run_loop(self, base_params: Dict[str, Any], count: int, settings):
        diagnostics = Diagnostics(settings.logs_dir, filename="batch_video_errors.log")
        for i in range(count):
            if self.cancel_event.is_set():
                break

            with self.lock:
                self.current_index = i + 1
                self.log.append(f"🎬 [Video {i+1}/{count}] Đang tìm chủ đề mới và dựng video...")

            try:
                run_params = deepcopy(base_params)

                def progress_cb(evt):
                    msg = evt.get("message", "")
                    if msg:
                        with self.lock:
                            self.log.append(f"  • {msg}")

                project_path = run_auto(
                    **run_params,
                    settings=settings,
                    progress_cb=progress_cb,
                    cancel_event=self.cancel_event
                )

                with self.lock:
                    self.created_projects.append(str(project_path))
                    self.log.append(f"✅ [Video {i+1}/{count}] Hoàn tất: {Path(project_path).name}")

            except Exception as e:
                diagnostics.record_exception(e, f"Batch run item {i+1}")
                with self.lock:
                    self.log.append(f"❌ [Video {i+1}/{count}] Lỗi: {diagnostics.redact(str(e))}")
                if self.cancel_event.is_set():
                    break

            # Short breath between videos
            time.sleep(1.0)

        with self.lock:
            if self.status == "running":
                self.status = "done"
                self.log.append(f"🎉 Hoàn thành sản xuất loạt video! Đã tạo {len(self.created_projects)}/{count} video.")
