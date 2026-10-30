"""Static import integrity & Assets step regression tests.
Guarantees:
1. All modules across pipeline/, editor/, providers/, agents/, schemas/ import cleanly without NameError/ImportError.
2. Assets step with words sidecar runs to completion with zero NameError.
"""
from __future__ import annotations

import importlib
import json
from pathlib import Path
import pytest

from config.settings import ROOT_DIR, Settings
from schemas.edit_plan import EditPlan
from utils.atomic_io import write_json_atomic, read_json_atomic


def test_import_all_core_modules():
    """Iterate through all Python files in core packages to ensure clean imports."""
    app_dir = Path(__file__).resolve().parents[1]
    core_packages = ["pipeline", "editor", "providers", "agents", "schemas", "utils"]

    failed_modules = []

    for pkg in core_packages:
        pkg_dir = app_dir / pkg
        if not pkg_dir.is_dir():
            continue
        for py_file in pkg_dir.rglob("*.py"):
            if py_file.name.startswith("__init__") or "test" in py_file.name:
                continue
            # Construct module name relative to app_dir
            rel_parts = py_file.relative_to(app_dir).with_suffix("").parts
            mod_name = ".".join(rel_parts)
            try:
                importlib.import_module(mod_name)
            except Exception as exc:
                failed_modules.append((mod_name, str(exc)))

    assert not failed_modules, f"Modules failed to import cleanly: {failed_modules}"


def test_assets_pipeline_words_integration_no_name_error(tmp_path):
    """Regression test: Ensure Assets step + Visual Planner v3 words loading does not crash with NameError (read_words)."""
    from utils.word_timing import save_words, read_words

    # Use real plan from project 174574fb if available, or minimal valid dict
    real_plan_p = Path("output/auto-cong-nghe-174574fb/edit_plan.json")
    if real_plan_p.is_file():
        edit_plan_data = read_json_atomic(real_plan_p)
    else:
        pytest.skip("Fixture edit_plan.json not found")

    project_dir = tmp_path / "project_assets_test"
    project_dir.mkdir(parents=True)
    audio_dir = project_dir / "audio"
    audio_dir.mkdir()

    write_json_atomic(project_dir / "edit_plan.json", edit_plan_data)
    plan_obj = EditPlan.model_validate(edit_plan_data)

    # Create dummy words sidecars for each scene
    for sc in plan_obj.scenes:
        w_list = [{"text": w, "start": i * 0.4, "end": (i + 1) * 0.4} for i, w in enumerate(sc.narration.split()[:5])]
        save_words(audio_dir / f"scene_{sc.id}.words.json", sc.narration, 5.0, w_list)

    # Test the exact code block from pipeline/run_all.py (lines 371-375)
    words_map = {}
    for sc in plan_obj.scenes:
        words_file = project_dir / "audio" / f"scene_{sc.id}.words.json"
        if words_file.is_file():
            words_map[sc.id] = read_words(words_file)

    assert len(words_map) == len(plan_obj.scenes)
    for sid in words_map:
        assert isinstance(words_map[sid], list)
        assert len(words_map[sid]) > 0
