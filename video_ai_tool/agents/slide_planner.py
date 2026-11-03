"""Slide Planner Agent for Light Glass theme.

Plans 5-10 slides (~6.5s per slide) covering 100% of narration sentences,
assigning distinct layouts, extracting grounded slots, and falling back
to deterministic heuristic mapper if LLM fails.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from config.settings import get_settings
from editor.motion.light_glass_slots import create_heuristic_slide_script
from editor.motion.slide_grounding import verify_and_ground_slides
from schemas.slide_script import (
    SlideScript,
    SlideItem,
    SourceRef,
    EmphasisItem,
)
from utils.diagnostics import Diagnostics

logger = logging.getLogger(__name__)


SLIDE_PLANNER_PROMPT_TEMPLATE = """Bạn là Slide Planner chuyên nghiệp cho video tin tức công nghệ phong cách Light Glass (9:16 vertical).
Nhiệm vụ của bạn là gom toàn bộ các câu trong lời đọc thành {target_slides} slide (mỗi slide kéo dài khoảng 5-8 giây, gồm 1-3 câu liên tiếp).

THÔNG TIN ĐẦU VÀO:
- Chủ đề: {topic}
- Tổng thời lượng: {total_duration:.2f}s
- Nguồn tin: {source_info}
- Danh sách sự kiện & số liệu kiểm chứng (Brief Facts):
{brief_facts}

- Danh sách các câu lời đọc ({num_sentences} câu):
{sentences_text}

QUY TẮC BẮT BUỘC (TUÂN THỦ 100%):
1. Phủ kín 100% các câu, không bỏ sót câu nào. Mỗi slide gồm 1-3 câu liên tiếp (sentence_ids liên tục).
2. Layouts hợp lệ theo kiến trúc Two-Zone Split (Tầng 1 Mockup trực quan, Tầng 2 Card văn bản lớn):
   - lg_source_headline: Tầng 1 là Card nguồn/repo mockup, Tầng 2 là Headline 3 dòng in hoa cực lớn (BẮT BUỘC cho slide 1).
   - lg_stat_hero: Tầng 1 là Dark Console Card với các ô chỉ số, Tầng 2 là con số lớn màu xanh dương kèm nhãn giải thích (chỉ dùng khi câu có con số cụ thể).
   - lg_shot_features: Tầng 1 là Cửa sổ web bảng điều khiển, Tầng 2 là danh sách 2-3 điểm nổi bật (mỗi điểm có chấm tròn xanh).
   - lg_vs_compare: Thẻ so sánh 2 vế xếp dọc (cũ/thủ công vs mới/tự động) kèm chữ VS ở giữa và badge WINNER.
   - lg_note_card: Thẻ đơn trung tâm với pill TIẾT KIỆM và nhận định/đúc kết chuyên gia (tối đa 3 dòng).
   - lg_cta_profile: Thẻ hồ sơ kênh Facebook/MXH với avatar tròn, 2 nút hành động và bong bóng reaction (BẮT BUỘC cho slide cuối cùng).
3. KHÔNG ĐƯỢC lặp layout ở 2 slide liền kề.
4. TUYỆT ĐỐI KHÔNG BỊA SỐ LIỆU HOẶC TÊN RIÊNG: Mọi con số trong slot 'value' hoặc slot chữ PHẢI xuất hiện nguyên văn trong câu đọc của slide đó hoặc trong Brief Facts.
5. Giới hạn độ dài slot:
   - headline / title: tối đa 3 dòng, mỗi dòng <= 14 ký tự (tổng <= 42 ký tự).
   - pill / badge: tối đa 28 ký tự.
   - features items: tối đa 3-4 ý, mỗi ý <= 40 ký tự.
   - compare: mỗi bên <= 2 dòng x 14 ký tự.
6. Trích xuất 1-2 cụm từ nhấn (emphasis): mỗi cụm <= 3 từ, PHẢI xuất hiện NGUYÊN VĂN trong câu đọc của slide đó.
7. Với MỖI slide, BẮT BUỘC viết một 'image_prompt' bằng tiếng Anh, mô tả chi tiết hình ảnh 5s trực quan sát ý nghĩa câu đọc, dễ hình dung, lôi cuốn, mang tính điện ảnh/concept art 3D (ví dụ: 'Cinematic hyper-realistic 3D render of futuristic automated humanoid robot in high-tech factory, dramatic lighting, 8k', 'Neon glowing financial spline line descending sharply towards zero in modern digital exchange, dark background, hologram numbers', v.v.).

ĐẦU RA CHỈ LÀ JSON HỢP LỆ VỚI CẤU TRÚC:
{{
  "slides": [
    {{
      "id": "slide_1",
      "layout": "lg_source_headline",
      "sentence_ids": [1],
      "image_prompt": "Cinematic 3D concept art of...",
      "slots": {{
        "pill": "TIÊU ĐIỂM CÔNG NGHỆ",
        "title": "TIÊU ĐỀ NGẮN",
        "text": "Tóm tắt lời đọc..."
      }},
      "emphasis": [
        {{"phrase": "từ khóa 1", "kind": "term"}}
      ]
    }},
    ...
  ]
}}
"""


def _format_sentences_for_prompt(sentences: list[dict[str, Any]]) -> str:
    lines = []
    for s in sentences:
        s_id = s.get("id", 0)
        s_txt = s.get("text", "")
        s_dur = float(s.get("end", 0.0)) - float(s.get("start", 0.0))
        lines.append(f"Câu {s_id} ({s_dur:.1f}s): {s_txt}")
    return "\n".join(lines)


def _format_brief_facts_for_prompt(brief: Any) -> str:
    if not brief:
        return "Không có facts bổ sung."
    facts = getattr(brief, "facts", None) or (brief.get("facts") if isinstance(brief, dict) else [])
    if not facts:
        return "Không có facts bổ sung."
    lines = []
    for i, f in enumerate(facts[:8]):
        claim = getattr(f, "claim", "") or (f.get("claim") if isinstance(f, dict) else "")
        quote = getattr(f, "evidence_quote", "") or (f.get("evidence_quote") if isinstance(f, dict) else "")
        lines.append(f"- Fact {i+1}: {claim}" + (f" (Trích dẫn: '{quote}')" if quote else ""))
    return "\n".join(lines)


def plan_slides(
    brief: Any,
    sentences: list[dict[str, Any]],
    total_duration: float = 0.0,
    settings: Any = None,
    diagnostics: Diagnostics | None = None,
    llm_client: Any = None,
    brand_name: str = "TIN CÔNG NGHỆ",
) -> SlideScript:
    """Plan SlideScript with LLM router and verify through code grounding.
    
    Falls back to heuristic mapper if LLM fails or is disabled.
    """
    if not sentences:
        return SlideScript(topic="Chưa có dữ liệu", total_duration=0.0, slides=[])

    settings = settings or get_settings()
    diagnostics = diagnostics or Diagnostics(settings.logs_dir, filename="slide_planner.log")

    if total_duration <= 0.0:
        total_duration = float(sentences[-1].get("end", 0.0))

    target_slides = max(5, min(10, round(total_duration / 6.5)))
    if len(sentences) < target_slides:
        target_slides = max(1, len(sentences))

    sentences_by_id = {int(s.get("id", i + 1)): s for i, s in enumerate(sentences)}

    # Topic and Source info
    topic = ""
    source_info = "Tin tức công nghệ"
    if brief:
        topic = str(getattr(brief, "topic", "") or (brief.get("topic") if isinstance(brief, dict) else ""))
        facts = getattr(brief, "facts", None) or (brief.get("facts") if isinstance(brief, dict) else [])
        if facts:
            first_fact = facts[0]
            s_url = getattr(first_fact, "source_url", "") or (first_fact.get("source_url") if isinstance(first_fact, dict) else "")
            s_name = getattr(first_fact, "source_name", "") or (first_fact.get("source_name") if isinstance(first_fact, dict) else "")
            source_info = f"{s_name} ({s_url})"

    prompt = SLIDE_PLANNER_PROMPT_TEMPLATE.format(
        target_slides=target_slides,
        topic=topic or "Bản tin công nghệ",
        total_duration=total_duration,
        source_info=source_info,
        brief_facts=_format_brief_facts_for_prompt(brief),
        num_sentences=len(sentences),
        sentences_text=_format_sentences_for_prompt(sentences),
    )

    # Estimate tokens
    est_in_tokens = max(100, len(prompt) // 4)
    est_out_tokens = max(100, target_slides * 120)
    est_cost = (est_in_tokens * 0.15 + est_out_tokens * 0.60) / 1_000_000
    logger.info("Slide Planner token estimate: ~%d in, ~%d out (~$%.5f)", est_in_tokens, est_out_tokens, est_cost)

    slide_script: SlideScript | None = None

    # Call LLM or fallback
    try:
        raw_response_text = None
        if llm_client is not None:
            # For testing with injected mock
            raw_response_text = llm_client.text(prompt)
        else:
            from providers.llm.router import Router, route_ready
            step_name = "researcher"
            if route_ready(settings, step_name):
                router = Router(settings, step=step_name, diagnostics=diagnostics)
                raw_response_text = router.text(prompt)
            elif route_ready(settings, "director"):
                router = Router(settings, step="director", diagnostics=diagnostics)
                raw_response_text = router.text(prompt)

        if raw_response_text:
            # Parse JSON
            cleaned_json = raw_response_text.strip()
            if "```" in cleaned_json:
                # Strip markdown code blocks
                parts = cleaned_json.split("```")
                for p in parts:
                    p_strip = p.strip()
                    if p_strip.startswith("json"):
                        p_strip = p_strip[4:].strip()
                    if p_strip.startswith("{") and p_strip.endswith("}"):
                        cleaned_json = p_strip
                        break

            data = json.loads(cleaned_json)
            raw_slides = data.get("slides", [])
            parsed_slides: list[SlideItem] = []

            for s_idx, rs in enumerate(raw_slides):
                s_id = str(rs.get("id") or f"slide_{s_idx + 1}")
                s_layout = str(rs.get("layout") or "lg_note_card")
                s_sids = [int(x) for x in rs.get("sentence_ids", []) if int(x) in sentences_by_id]
                if not s_sids:
                    s_sids = [min(sentences_by_id.keys())]

                s_start = min(float(sentences_by_id[sid].get("start", 0.0)) for sid in s_sids)
                s_end = max(float(sentences_by_id[sid].get("end", 0.0)) for sid in s_sids)
                s_dur = max(0.1, s_end - s_start)
                s_narration = " ".join(sentences_by_id[sid].get("text", "") for sid in s_sids)

                # Parse emphasis
                raw_emp = rs.get("emphasis", [])
                emp_items = []
                for emp in raw_emp:
                    if isinstance(emp, dict) and emp.get("phrase"):
                        emp_items.append(
                            EmphasisItem(
                                phrase=str(emp["phrase"]).strip(),
                                kind=emp.get("kind", "term"),
                            )
                        )

                slide_item = SlideItem(
                    id=s_id,
                    layout=s_layout,  # type: ignore
                    sentence_ids=s_sids,
                    slots=rs.get("slots", {}),
                    emphasis=emp_items,
                    t_start=round(s_start, 3),
                    t_end=round(s_end, 3),
                    duration=round(s_dur, 3),
                    narration=s_narration,
                )
                parsed_slides.append(slide_item)

            if parsed_slides:
                slide_script = SlideScript(
                    topic=topic or "Bản tin công nghệ",
                    total_duration=round(total_duration, 3),
                    slides=parsed_slides,
                    repair_notes=["Sinh bằng LLM Slide Planner."],
                )

    except Exception as exc:
        diagnostics.record_exception(exc, "Slide Planner LLM call failed, falling back to heuristic")
        logger.warning("Slide Planner LLM call failed: %s. Using heuristic fallback.", exc)

    # Fallback to heuristic mapper if LLM produced nothing valid
    if slide_script is None or not slide_script.slides:
        slide_script = create_heuristic_slide_script(
            sentences=sentences,
            brief=brief,
            total_duration=total_duration,
            brand_name=brand_name,
        )

    # Code-level Grounding & Verification
    verified_script = verify_and_ground_slides(
        slide_script=slide_script,
        sentences_by_id=sentences_by_id,
        brief=brief,
    )
    return verified_script
