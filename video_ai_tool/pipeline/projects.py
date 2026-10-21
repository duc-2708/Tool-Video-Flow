# file: pipeline/projects.py
"""Quản lý project dạng thư mục, dùng chung cho các trang pipeline."""
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from schemas.research_brief import ResearchBrief
from utils.cache import write_json
from utils.atomic_io import read_json_atomic
from utils.text import clean_text, slugify


@dataclass(frozen=True)
class Project:
    name: str
    path: Path
    topic: str
    has_brief: bool


def project_path(output_dir: Path, name: str) -> Path:
    root = output_dir.resolve()
    candidate = (root / name).resolve()
    if not name or candidate.parent != root or name != candidate.name or candidate.is_symlink():
        raise ValueError("Thư mục project không hợp lệ.")
    return candidate


def read_json(path: Path, *, allow_stale: bool = False) -> dict:
    return read_json_atomic(path, allow_stale=allow_stale)


def load_brief(project: Path) -> ResearchBrief:
    return ResearchBrief.model_validate(read_json(project / "brief.json"))


def list_projects(output_dir: Path) -> list[Project]:
    if not output_dir.exists():
        return []
    projects = []
    for path in sorted(output_dir.iterdir(), key=lambda item: item.name):
        if not path.is_dir() or path.is_symlink() or path.name.startswith(".") or path.name == "source_debug":
            continue
        safe_path = project_path(output_dir, path.name)
        topic = path.name
        for filename in ("brief.json", "project.json"):
            try:
                title = read_json(safe_path / filename).get("topic")
                if isinstance(title, str) and title.strip():
                    topic = title
                    break
            except (OSError, ValueError):
                continue
        projects.append(Project(path.name, safe_path, topic, (safe_path / "brief.json").is_file()))
    return projects


def create_project(output_dir: Path, topic: str) -> Path:
    topic = clean_text(topic)
    if not topic or len(topic) > 500:
        raise ValueError("Chủ đề phải có 1–500 ký tự.")
    output_dir.mkdir(parents=True, exist_ok=True)
    path = project_path(output_dir, f"{slugify(topic)}-{uuid4().hex[:8]}")
    path.mkdir()
    write_json(path / "project.json", {"topic": topic, "created_at": datetime.now(timezone.utc).isoformat()})
    return path
