"""Batch runner for producing multiple distinct videos automatically."""
from copy import deepcopy
from pathlib import Path
import threading
import time
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
            if self.thread is not None and self.thread.is_alive():
                return True
            return self.status == "running"

    def snapshot(self) -> Dict[str, Any]:
        with self.lock:
            thread_alive = bool(self.thread is not None and self.thread.is_alive())
            return {
                "status": self.status,
                "current_index": self.current_index,
                "total_count": self.total_count,
                "created_projects": list(self.created_projects),
                "log": list(self.log[-25:]),
                "thread_alive": thread_alive,
            }

    def cancel(self):
        """Yêu cầu dừng hợp tác ở điểm an toàn mà không ép status 'cancelled' ngay."""
        with self.lock:
            if self.status == "running" or (self.thread is not None and self.thread.is_alive()):
                self.cancel_event.set()
                self.log.append("Yêu cầu dừng chạy loạt ở điểm an toàn...")

    def start_batch(self, params: Dict[str, Any], count: int, settings=None):
        with self.lock:
            # Chỉ cho bắt đầu lô mới khi luồng cũ đã kết thúc (thread không còn alive)
            if self.thread is not None and self.thread.is_alive():
                return False
            if self.status == "running":
                return False
            self.status = "running"
            self.current_index = 0
            self.total_count = count
            self.created_projects = []
            self.log = [f"Bắt đầu tạo tự động loạt {count} video..."]
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
                self.log.append(f"[Video {i+1}/{count}] Đang tìm chủ đề mới và dựng video...")

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
                    self.log.append(f"[Video {i+1}/{count}] Hoàn tất: {Path(project_path).name}")

            except Exception as e:
                diagnostics.record_exception(e, f"Batch run item {i+1}")
                with self.lock:
                    self.log.append(f"[Video {i+1}/{count}] Lỗi: {diagnostics.redact(str(e))}")
                if self.cancel_event.is_set():
                    break

            time.sleep(1.0)

        with self.lock:
            if self.cancel_event.is_set():
                self.status = "cancelled"
                self.log.append(f"Đã dừng an toàn. Hoàn tất {len(self.created_projects)}/{count} video.")
            elif self.status == "running":
                self.status = "done"
                self.log.append(f"Hoàn thành sản xuất loạt video! Đã tạo {len(self.created_projects)}/{count} video.")
