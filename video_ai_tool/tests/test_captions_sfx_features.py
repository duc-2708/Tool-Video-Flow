"""Tests for refined small font captions, white-yellow-red palette, dynamic animations and Concat SFX."""
from pathlib import Path
from types import SimpleNamespace
import numpy as np
from PIL import Image
import pytest

from config.settings import ROOT_DIR
from editor.captions import find_font, is_standout_word, Captions, wrap_lines
from editor.motion.sfx import synthesize, ensure_sfx
from schemas.style import CaptionStyle
from schemas.visual import Visual, VisualData


def test_font_priority_picks_concat_fonts():
    font_path = find_font(ROOT_DIR)
    assert font_path.is_file()
    name = font_path.name
    # Should pick Montserrat, Inter or Phudu
    assert any(k in name for k in ("Montserrat", "Inter", "DTPhudu", "SpaceGrotesk", "arial"))


def test_is_standout_word_classification():
    # Numbers and percentages
    assert is_standout_word("75%") is True
    assert is_standout_word("100") is True
    assert is_standout_word("$10B") is True
    assert is_standout_word("15.5") is True
    assert is_standout_word("+50%") is True

    # High impact Vietnamese keywords
    assert is_standout_word("kỷ lục") is True
    assert is_standout_word("đột phá") is True
    assert is_standout_word("bùng nổ") is True
    assert is_standout_word("nguy hiểm") is True
    assert is_standout_word("bí mật") is True

    # Uppercase acronyms
    assert is_standout_word("AI") is True
    assert is_standout_word("CEO") is True
    assert is_standout_word("TOP") is True

    # Normal words
    assert is_standout_word("của") is False
    assert is_standout_word("và") is False
    assert is_standout_word("trong") is False
    assert is_standout_word("những") is False


def test_caption_style_schema_defaults():
    style = CaptionStyle()
    assert style.font_scale == 0.044  # smaller font scale
    assert style.color == "#FFFFFF"  # primary white
    assert style.highlight_color == "#FFE14A"  # accent yellow
    assert style.standout_color == "#FF3344"  # standout red


def test_synthesize_all_sfx_types():
    expected_types = ("click", "pop", "whoosh", "chime", "snap", "punch", "ding", "sparkle", "swoosh")
    for kind in expected_types:
        samples = synthesize(kind)
        assert isinstance(samples, np.ndarray)
        assert len(samples) > 0
        assert np.max(np.abs(samples)) <= 0.20


def test_ensure_sfx_generates_all_wav_files(tmp_path):
    ensure_sfx(tmp_path)
    expected = ["click.wav", "pop.wav", "whoosh.wav", "chime.wav", "snap.wav", "punch.wav", "ding.wav", "sparkle.wav", "swoosh.wav"]
    for fname in expected:
        p = tmp_path / fname
        assert p.is_file(), f"Missing SFX file: {fname}"
        assert p.stat().st_size > 0


def test_captions_overlay_renders_with_custom_palette(tmp_path):
    font_path = find_font(ROOT_DIR)
    dummy_audio = tmp_path / "scene_1.mp3"
    dummy_audio.write_bytes(b"\x00" * 100)

    timing_file = tmp_path / "scene_1.words.json"
    timing_file.write_text(
        '{"words": [{"text": "Việt", "start": 0.0, "end": 0.5}, {"text": "Nam", "start": 0.5, "end": 1.0}, {"text": "đạt", "start": 1.0, "end": 1.5}, {"text": "100%", "start": 1.5, "end": 2.0}]}',
        encoding="utf-8",
    )

    shot = SimpleNamespace(start=0.0, duration=2.5, path=None, spec=SimpleNamespace(visual=None))
    scene = SimpleNamespace(
        spec=SimpleNamespace(id=1, narration="Việt Nam đạt 100%"),
        audio=dummy_audio,
        duration=2.5,
        start=0.0,
        shots=[shot],
    )
    plan = SimpleNamespace(render_style=SimpleNamespace(captions=CaptionStyle()))
    timeline = SimpleNamespace(scenes=[scene], plan=plan, duration=2.5)

    captions = Captions(timeline, (1080, 1920), font_path)
    assert len(captions.entries) > 0

    # Frame at 0.2s: word 'Việt' active (normal -> yellow #FFE14A)
    overlay_1 = captions.overlay(0.2)
    assert overlay_1 is not None
    assert isinstance(overlay_1, Image.Image)

    # Frame at 1.7s: word '100%' active (standout -> red #FF3344)
    overlay_2 = captions.overlay(1.7)
    assert overlay_2 is not None
    assert isinstance(overlay_2, Image.Image)


def test_motion_css_and_engine_css_have_refined_caption_size():
    base_css = (Path(__file__).parent.parent / "editor/motion/base.css").read_text(encoding="utf-8")
    assert "font-size:42px" in base_css or "font-size: 42px" in base_css
    assert "wordPulse" in base_css
    assert "#FF3344" in base_css

    kit_css = (Path(__file__).parent.parent / "editor/motion/kit/kit.css").read_text(encoding="utf-8")
    assert "--kit-bg" in kit_css
    assert "--kit-card" in kit_css
