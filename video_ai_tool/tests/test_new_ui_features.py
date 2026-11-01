"""Unit test for new UI components: Batch Jobs, Video Warehouse, Settings View."""
import pytest
from pathlib import Path
from config.settings import Settings
from pipeline.batch_jobs import BatchJobs
from app.views.settings_view import update_env_file


def test_batch_jobs_singleton_and_status():
    b1 = BatchJobs()
    b2 = BatchJobs()
    assert b1 is b2
    snap = b1.snapshot()
    assert "status" in snap
    assert "created_projects" in snap
    assert snap["status"] in {"idle", "running", "done", "cancelled"}


def test_update_env_file(tmp_path: Path):
    env_file = tmp_path / ".env"
    env_file.write_text("GEMINI_API_KEY=old_token\nGEMINI_MODEL=gemini-2.5-flash\n", encoding="utf-8")

    update_env_file(tmp_path, "GEMINI_API_KEY", "new_token_123")
    content = env_file.read_text(encoding="utf-8")
    assert "GEMINI_API_KEY=new_token_123" in content
    assert "old_token" not in content

    # Add new key
    update_env_file(tmp_path, "GATEWAY_API_KEY", "gateway_secret_456")
    content2 = env_file.read_text(encoding="utf-8")
    assert "GATEWAY_API_KEY=gateway_secret_456" in content2
