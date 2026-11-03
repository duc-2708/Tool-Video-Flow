"""Slide Planner Agent for Motion Kit v2.

Plans slides (~5.0s per slide, n = round(duration / 5)) covering 100% of narration sentences,
assigning distinct kit_* layouts without consecutive duplicates, extracting grounded slots,
and only assigning photo/chart layouts when real data exists. Falls back to deterministic
heuristic mapper if LLM fails.
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
    ChartSlot,
    PhotoSlot,
)
from utils.diagnostics import Diagnostics

logger = logging.getLogger(__name__)


SLIDE_PLANNER_PROMPT_TEMPLATE = """Bạn là Slide Planner chuyên nghiệp cho video trình chiếu Motion Kit v2 (9:16 vertical).
Nhiệm vụ của bạn là gom toàn bộ các câu trong lời đọc thành {target_slides} slide (mục tiêu ~5.0 giây mỗi slide, gồm 1-2 câu liên tiếp).

THÔNG TIN ĐẦU VÀO:
- Chủ đề: {topic}
- Tổng thời lượng: {total_duration:.2f}s
- Nguồn tin: {source_info}
- Danh sách sự kiện & số liệu kiểm chứng (Brief Facts):
{brief_facts}

- Danh sách các câu lời đọc ({num_sentences} câu):
{sentences_text}

QUY TẮC BẮT BUỘC (TUÂN THỦ 100%):
1. Phủ kín 100% các câu, không bỏ sót câu nào. Mỗi slide gồm 1-2 câu liên tiếp (sentence_ids liên tục).
2. Layouts hợp lệ trong Motion Kit v2:
   - kit_title: Tiêu đề lớn (tối đa 3 dòng x 14 ký tự), câu phụ, pill chủ đề (BẮT BUỘC cho slide 1).
   - kit_stat: Con số lớn, đơn vị, chú thích, delta tăng/giảm (CHỈ DÙNG KHI CÂU CÓ CON SỐ CỤ THỂ).
   - kit_chart_bar / kit_chart_line / kit_chart_donut: Biểu đồ trực quan vẽ từ dữ liệu (CHỈ DÙNG KHI CÓ DỮ LIỆU CHUỖI SỐ THẬT: series[{{label, value}}]).
   - kit_photo: Ảnh chân dung/tư liệu thật kèm chú thích tên/vai trò/nguồn (CHỈ DÙNG KHI CÓ ẢNH THẬT ĐƯỢC CẤP).
   - kit_list: Danh sách điểm nhấn nổi bật (tối đa 3-4 ý, mỗi ý <= 40 ký tự).
   - kit_compare: So sánh 2 vế đối chiếu (mỗi bên <= 2 dòng).
   - kit_quote: Trích dẫn phát biểu trực tiếp của nhân vật/chuyên gia kèm tên và vai trò.
   - kit_timeline: Tiến trình thời gian hoặc các mốc quan trọng (tối đa 4-5 mốc).
   - kit_outro: Kêu gọi theo dõi và nhận diện kênh (BẮT BUỘC cho slide cuối cùng).
3. KHÔNG ĐƯỢC lặp layout ở 2 slide liền kề.
4. TUYỆT ĐỐI KHÔNG BỊA SỐ LIỆU HOẶC TÊN RIÊNG: Mọi con số trong slot 'value' hoặc slot chữ PHẢI xuất hiện nguyên văn trong câu đọc của slide đó hoặc trong Brief Facts.
5. Giới hạn độ dài slot:
   - headline / title: tối đa 3 dòng, mỗi dòng <= 14 ký tự (tổng <= 42 ký tự).
   - pill / badge: tối đa 28 ký tự.
   - list items: tối đa 3-4 ý, mỗi ý <= 40 ký tự.
   - compare: mỗi bên <= 2 dòng x 14 ký tự.
6. Trích xuất 1-2 cụm từ nhấn (emphasis): mỗi cụm <= 3 từ, PHẢI xuất hiện NGUYÊN VĂN trong câu đọc của slide đó.
7. Với MỖI slide, viết một 'image_prompt' bằng tiếng Anh, mô tả chi tiết hình ảnh trực quan 5s sát ý nghĩa câu đọc.

ĐẦU RA CHỈ LÀ JSON HỢP LỆ VỚI CẤU TRÚC:
{{
  "slides": [
    {{
      "id": "slide_1",
      "layout": "kit_title",
      "sentence_ids": [1],
      "image_prompt": "Cinematic visual description...",
      "slots": {{
        "pill": "TIÊU ĐIỂM CÔNG NGHỆ",
        "title": "TIÊU ĐỀ NGẮN",
        "subtitle": "Tóm tắt lời đọc..."
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
    """Plan SlideScript with target ~5.0s per slide (n = round(duration / 5)).
    
    Guarantees no consecutive identical layouts and only assigns photo/chart layouts
    when real slot data exists.
    """
    if not sentences:
        return SlideScript(topic="Chưa có dữ liệu", total_duration=0.0, slides=[])

    settings = settings or get_settings()
    diagnostics = diagnostics or Diagnostics(settings.logs_dir, filename="slide_planner.log")

    if total_duration <= 0.0:
        total_duration = float(sentences[-1].get("end", 0.0))

    # Target 5s slides: n = round(duration / 5)
    target_slides = max(4, round(total_duration / 5.0))
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

    est_in_tokens = max(100, len(prompt) // 4)
    est_out_tokens = max(100, target_slides * 120)
    est_cost = (est_in_tokens * 0.15 + est_out_tokens * 0.60) / 1_000_000
    logger.info("Slide Planner token estimate: ~%d in, ~%d out (~$%.5f)", est_in_tokens, est_out_tokens, est_cost)

    slide_script: SlideScript | None = None

    # Call LLM or fallback
    try:
        raw_response_text = None
        if llm_client is not None:
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
            cleaned_json = raw_response_text.strip()
            if "```" in cleaned_json:
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
                s_layout = str(rs.get("layout") or "kit_title")
                s_sent_ids = [int(x) for x in rs.get("sentence_ids", []) if int(x) in sentences_by_id]
                if not s_sent_ids:
                    continue

                t_start = float(sentences_by_id[s_sent_ids[0]].get("start", 0.0))
                t_end = float(sentences_by_id[s_sent_ids[-1]].get("end", 0.0))
                s_dur = max(0.1, t_end - t_start)
                s_narration = " ".join(sentences_by_id[sid].get("text", "") for sid in s_sent_ids)

                slots = rs.get("slots") or {}
                # Anti-repetition rule: no consecutive identical layouts
                if parsed_slides and s_layout == parsed_slides[-1].layout:
                    alt_pool = ["kit_title", "kit_stat", "kit_list", "kit_compare", "kit_quote"]
                    s_layout = next((l for l in alt_pool if l != parsed_slides[-1].layout), "kit_title")

                # Photo/chart only when real data exists in slots
                if s_layout == "kit_photo" and not (slots.get("path") or slots.get("image") or slots.get("image_url")):
                    s_layout = "kit_title"
                if s_layout.startswith("kit_chart") and not (slots.get("series") or (rs.get("chart") and rs.get("chart", {}).get("series"))):
                    s_layout = "kit_stat" if slots.get("value") is not None else "kit_list"

                # Parse emphasis
                raw_emp = rs.get("emphasis") or []
                emp_items = []
                for e in raw_emp[:2]:
                    phr = str(e.get("phrase") or "").strip()
                    if phr:
                        emp_items.append(EmphasisItem(phrase=phr, kind=e.get("kind", "term")))

                parsed_slides.append(
                    SlideItem(
                        id=s_id,
                        layout=s_layout,
                        sentence_ids=s_sent_ids,
                        slots=slots,
                        emphasis=emp_items,
                        t_start=t_start,
                        t_end=t_end,
                        duration=s_dur,
                        narration=s_narration,
                        image_prompt=rs.get("image_prompt", ""),
                    )
                )

            if parsed_slides:
                slide_script = SlideScript(
                    topic=topic or "Bản tin công nghệ",
                    total_duration=total_duration,
                    slides=parsed_slides,
                )

    except Exception as e:
        logger.warning("LLM Slide Planning failed (%s); using deterministic heuristic mapper", e)
        if diagnostics:
            diagnostics.record_exception(e, "Slide Planner LLM failure")

    if not slide_script or not slide_script.slides:
        logger.info("Using deterministic heuristic mapper for SlideScript")
        slide_script = create_heuristic_slide_script(
            brief=brief,
            sentences=sentences,
            total_duration=total_duration,
            brand_name=brand_name,
        )

    # Verify and ground slides through deterministic code
    grounded_script = verify_and_ground_slides(slide_script, brief=brief)
    return grounded_script
