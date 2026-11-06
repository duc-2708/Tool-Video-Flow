"""Tests for Slide Image Resolver and Visual Prompt Generation."""
from pathlib import Path
from PIL import Image

from schemas.slide_script import SlideScript, SlideItem
from editor.motion.light_glass_slots import _generate_vivid_image_prompt
from pipeline.slide_image_resolver import (
    generate_cinematic_visual,
    path_to_data_uri,
    resolve_images_for_slide_script,
)


def test_generate_vivid_image_prompts():
    # 1. Author prompt
    p1 = _generate_vivid_image_prompt("Elon Musk chia sẻ về tương lai", author="Elon Musk", idx=0)
    assert "Elon Musk" in p1
    assert "Cinematic" in p1

    # 2. Savings / Piggy bank prompt
    p2 = _generate_vivid_image_prompt("Tiết kiệm tiền vào heo đất truyền thống")
    assert "piggy bank" in p2.lower()

    # 3. Robotics prompt
    p3 = _generate_vivid_image_prompt("Robot tự động hóa sản xuất trong nhà máy")
    assert "robot" in p3.lower()

    # 4. Neural AI prompt
    p4 = _generate_vivid_image_prompt("Mô hình trí tuệ nhân tạo AI và mạng thần kinh")
    assert "neural" in p4.lower() or "ai" in p4.lower()

    # 5. Risk shield prompt
    p5 = _generate_vivid_image_prompt("Cảnh báo rủi ro lạm phát và bảo vệ tài sản")
    assert "shield" in p5.lower() or "risk" in p5.lower()


def test_generate_cinematic_visual(tmp_path: Path):
    target_png = tmp_path / "test_visual.png"
    prompt = "Vibrant glowing cybernetic neural network core pulsating with complex interconnected data nodes"
    out_path = generate_cinematic_visual(prompt=prompt, output_path=target_png, width=640, height=640)
    
    assert out_path.is_file()
    assert out_path.stat().st_size > 5000  # Non-trivial size
    with Image.open(out_path) as img:
        assert img.size == (640, 640)
        assert img.mode == "RGB"


def test_path_to_data_uri(tmp_path: Path):
    dummy_file = tmp_path / "sample.png"
    img = Image.new("RGB", (100, 100), color=(10, 20, 30))
    img.save(dummy_file, "PNG")

    uri = path_to_data_uri(dummy_file)
    assert uri is not None
    assert uri.startswith("data:image/png;base64,")


def test_resolve_images_for_slide_script(tmp_path: Path, monkeypatch):
    project_dir = tmp_path / "test_project"
    project_dir.mkdir(parents=True, exist_ok=True)

    slides = [
        SlideItem(
            id="slide_1",
            layout="lg_source_headline",
            sentence_ids=[1],
            narration="Elon Musk phát biểu về trí tuệ nhân tạo",
            slots={"pill": "TIN MỚI", "title": "Elon Musk nói gì", "text": "Elon Musk phát biểu"},
            image_prompt="Cinematic portrait of Elon Musk in cyber studio",
        ),
        SlideItem(
            id="slide_2",
            layout="lg_stat_hero",
            sentence_ids=[2],
            narration="Sản xuất vi mạch bán dẫn và chip AI đạt kỷ lục mới",
            slots={"pill": "SỐ LIỆU", "value": "300", "unit": "%"},
            image_prompt="High-tech financial spline curve plunging to zero cost",
        ),
    ]
    ss = SlideScript(topic="Công nghệ AI", total_duration=10.0, slides=slides)

    call_count = [0]
    def fake_download(q, target_path, **kwargs):
        call_count[0] += 1
        im = Image.new("RGB", (1080, 1080), color=(15 * call_count[0], 20, 30))
        target_path.parent.mkdir(parents=True, exist_ok=True)
        im.save(target_path, "PNG")
        if "out_match_info" in kwargs and kwargs["out_match_info"] is not None:
            kwargs["out_match_info"]["reason"] = "Khớp thực thể test"
        return True

    monkeypatch.setattr("pipeline.slide_image_resolver.download_real_web_image", fake_download)

    resolved = resolve_images_for_slide_script(project_dir, ss)
    assert len(resolved) == 2
    for r in resolved:
        assert Path(r).is_file()
        assert Path(r).stat().st_size > 1000
    assert "image_url" in ss.slides[0].slots
    assert "image_url" in ss.slides[1].slots


def test_diverse_12_beat_visuals(tmp_path: Path):
    """Ensure all 12 beats generate distinct, varied imagery and no false AI substring matches."""
    prompts = [
        _generate_vivid_image_prompt("Cảnh 1 về tác giả", author="Elon Musk", idx=i)
        for i in range(12)
    ]
    # All 12 prompts must be non-empty and diverse
    assert len(set(prompts)) == 12

    # Verify that words containing 'ai' like 'portrait' or 'against' do not all collapse into neural_net
    img_dir = tmp_path / "diverse_beats"
    img_dir.mkdir(parents=True, exist_ok=True)
    generated = []
    for i, p in enumerate(prompts):
        out_f = img_dir / f"beat_{i+1:02d}.png"
        generate_cinematic_visual(prompt=p, output_path=out_f, width=480, height=480)
        assert out_f.is_file()
        generated.append(out_f.stat().st_size)

    # High diversity of file sizes (at least 8 distinct file sizes out of 12)
    assert len(set(generated)) >= 8

