"""Visual Planner v3: Activity-rich motion visual planning with Prompt B and registry elements."""
import json
import math
import re
import unicodedata
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable, get_args

from config.settings import Settings
from schemas.research_brief import ResearchBrief
from schemas.edit_plan import EditPlan, Scene
from schemas.visual import VisualData, VisualBeat, VisualBar
from schemas.motion_scene import MotionScenePlan, SceneCamera, SceneType
from schemas.visual_v3 import (
    VisualPlanResponse,
    VisualScene,
    VisualElement,
    VisualAnnotation,
    VisualMascot,
    VisualSFX,
    CentralMetaphor,
    normalize_visual_v3_payload,
)
from editor.motion.registry import REGISTRY, ElementRegistry, match_illustration_for_topic, list_available_illustrations
from utils.atomic_io import write_json_atomic, read_json_atomic
from utils.diagnostics import Diagnostics
from utils.word_timing import read_words, estimate_words


def _log_director_error(message: str, error: Exception | None = None, diagnostics: Diagnostics | None = None) -> None:
    """Log error to logs/director_errors.log with credential redaction."""
    try:
        log_dir = Path("logs")
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "director_errors.log"
        err_msg = f": {type(error).__name__} - {str(error)}" if error else ""
        text = f"[VisualPlannerV3] {message}{err_msg}\n"
        if diagnostics is not None:
            text = diagnostics.redact(text)
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(text)
    except Exception:
        pass


def find_prompt_path(filename: str, settings: Settings) -> Path:
    """Find prompt file across candidate locations without modifying settings."""
    candidates = [
        settings.prompts_dir / filename,
        Path(__file__).resolve().parents[1] / "prompts" / filename,
    ]
    for p in candidates:
        if p.is_file():
            return p
    raise FileNotFoundError(f"Không tìm thấy file prompt '{filename}'.")


def render_visual_prompt(
    template_text: str,
    plan: EditPlan,
    brief: ResearchBrief | None = None,
    registry: ElementRegistry = REGISTRY,
) -> str:
    """Fill dynamic registry catalog and formatted script scenes into Prompt B."""
    total_sec = sum(getattr(s, "duration_sec", 0.0) or 8.0 for s in plan.scenes)
    if total_sec <= 0:
        total_sec = plan.duration_sec or 45.0
    sec = int(total_sec)
    scene_count = len(plan.scenes)

    script_lines: list[str] = []
    for sc in plan.scenes:
        facts_str = f" [Facts: {', '.join(str(f) for f in sc.fact_ids)}]" if sc.fact_ids else ""
        role_str = getattr(sc, "role", "explain")
        script_lines.append(f"CẢNH {sc.id} ({role_str}){facts_str}:")
        script_lines.append(f"Lời đọc: {sc.narration}")
        script_lines.append("")

    script_text = "\n".join(script_lines)

    rendered = template_text.replace("{ELEMENT_CATALOG}", registry.catalog_prompt_string())
    rendered = rendered.replace("{SECONDS}", str(sec))
    rendered = rendered.replace("{S}", str(scene_count))
    rendered = rendered.replace("<<<DÁN KỊCH BẢN VÀO ĐÂY>>>", script_text)
    rendered = rendered.replace("{SCRIPT}", script_text)
    return rendered


def normalize_phrase_token(text: str) -> str:
    """Strip diacritics, lowercase, and remove punctuation for robust fuzzy matching."""
    norm = unicodedata.normalize("NFD", str(text).casefold()).replace("đ", "d")
    return "".join(c for c in norm if c.isalnum() and not unicodedata.combining(c))


def match_at_phrase_to_seconds(
    at_phrase: str,
    words: list[dict[str, Any]],
    scene_duration: float,
    elem_idx: int = 0,
    total_elems: int = 1,
) -> tuple[float, bool]:
    """
    Fuzzy match an at_phrase to seconds using words.json word boundaries.
    Returns (at_sec, is_matched).
    If no match, returns evenly distributed timestamp within scene_duration and is_matched=False.
    """
    if not at_phrase or not at_phrase.strip():
        step = scene_duration / max(1, total_elems + 1)
        fallback = round(min(scene_duration, max(0.2, (elem_idx + 1) * step)), 2)
        return fallback, False

    phrase_tokens = [normalize_phrase_token(w) for w in at_phrase.split() if normalize_phrase_token(w)]
    if not phrase_tokens or not words:
        step = scene_duration / max(1, total_elems + 1)
        fallback = round(min(scene_duration, max(0.2, (elem_idx + 1) * step)), 2)
        return fallback, False

    words_tokens = [normalize_phrase_token(w.get("text", "")) for w in words]
    p_len = len(phrase_tokens)

    # 1. Exact consecutive sublist match
    for i in range(len(words_tokens) - p_len + 1):
        if words_tokens[i : i + p_len] == phrase_tokens:
            try:
                start = float(words[i].get("start", 0.0))
                return round(start, 2), True
            except (ValueError, TypeError):
                break

    # 2. Sub-slice match if phrase has >= 2 tokens
    if p_len >= 2:
        for sub_len in range(p_len - 1, 1, -1):
            for start_idx in range(p_len - sub_len + 1):
                sub_phrase = phrase_tokens[start_idx : start_idx + sub_len]
                for i in range(len(words_tokens) - sub_len + 1):
                    if words_tokens[i : i + sub_len] == sub_phrase:
                        try:
                            start = float(words[i].get("start", 0.0))
                            return round(start, 2), True
                        except (ValueError, TypeError):
                            break

    # 3. Non-trivial individual token match (>= 3 chars)
    for token in phrase_tokens:
        if len(token) >= 3:
            for i, w_token in enumerate(words_tokens):
                if w_token == token:
                    try:
                        start = float(words[i].get("start", 0.0))
                        return round(start, 2), True
                    except (ValueError, TypeError):
                        break

    # Fallback: evenly distributed timestamp
    step = scene_duration / max(1, total_elems + 1)
    fallback = round(min(scene_duration, max(0.2, (elem_idx + 1) * step)), 2)
    return fallback, False


def validate_and_repair_visual_plan(
    visual_resp: VisualPlanResponse,
    plan: EditPlan,
    brief: ResearchBrief | None = None,
    words_by_scene: dict[int, list[dict[str, Any]]] | None = None,
    registry: ElementRegistry = REGISTRY,
) -> tuple[VisualPlanResponse, list[str]]:
    """Validate VisualPlanResponse against Group 1/2/3 rules and perform auto-repair."""
    notes: list[str] = list(visual_resp.repair_notes)
    scenes_map = {sc.id: sc for sc in plan.scenes}
    brief_facts_text = ""
    if brief and getattr(brief, "facts", None):
        brief_facts_text = " ".join((f.fact_vi or f.claim) + " " + (f.evidence_quote or "") for f in brief.facts)

    previous_layout: str | None = None

    for sc_idx, v_scene in enumerate(visual_resp.scenes):
        sc_id = v_scene.scene_id
        edit_scene = scenes_map.get(sc_id) or (plan.scenes[sc_idx] if sc_idx < len(plan.scenes) else None)
        scene_narration = edit_scene.narration if edit_scene else ""
        scene_duration = getattr(edit_scene, "duration_sec", 0.0) or 8.0
        words = (words_by_scene or {}).get(sc_id, [])

        # 1. Layout Diversity Rule (No 2 consecutive scenes with identical layout)
        if previous_layout is not None and v_scene.layout == previous_layout:
            alt_layouts = ["center_hero", "split_2", "stack_3", "grid_4", "timeline_h"]
            new_layout = next((l for l in alt_layouts if l != previous_layout), "split_2")
            msg = f"[layout_diversity, nhóm 2] Cảnh {sc_id} trùng layout '{previous_layout}' với cảnh trước; đổi sang '{new_layout}'."
            notes.append(msg)
            v_scene.repair_notes.append(msg)
            v_scene.layout = new_layout  # type: ignore
        previous_layout = v_scene.layout

        # 2. Scene Density: Hook <= 2 elements, others <= 4 elements
        is_hook = sc_idx == 0 or v_scene.purpose == "hook"
        if is_hook:
            if len(v_scene.elements) > 2:
                msg = f"[scene_density, nhóm 2] Cảnh hook {sc_id} có {len(v_scene.elements)} phần tử (>2); giữ 2 phần tử lớn."
                notes.append(msg)
                v_scene.repair_notes.append(msg)
                v_scene.elements = v_scene.elements[:2]
            # Cảnh hook: tối thiểu 1 phần tử lớn (>=880px rộng hoặc số >=160px), không dùng danh sách 1 hàng nhỏ
            primary_elem = v_scene.elements[0] if v_scene.elements else None
            if primary_elem:
                c = primary_elem.content or {}
                items = c.get("items") or []
                if primary_elem.type in {"checklist", "steps_list", "steps_ladder", "timeline", "terminal_type", "magnifier_check", "list"} and len(items) <= 1:
                    if c.get("value") is not None or c.get("number_text"):
                        primary_elem.type = "stat_number"
                    else:
                        primary_elem.type = "stack_cards"
                        if len(items) <= 1:
                            c["items"] = [items[0] if items else "Thông tin mở đầu", "Chi tiết cơ chế", "Tác động thực tế"]
                    msg = f"[hook_hero, nhóm 2] Cảnh hook {sc_id}: chuyển danh sách 1 hàng sang phần tử lớn '{primary_elem.type}'."
                    notes.append(msg)
                    v_scene.repair_notes.append(msg)
        elif len(v_scene.elements) > 4:
            msg = f"[scene_density, nhóm 2] Cảnh {sc_id} có {len(v_scene.elements)} phần tử (>4); rút gọn còn 4."
            notes.append(msg)
            v_scene.repair_notes.append(msg)
            v_scene.elements = v_scene.elements[:4]

        # 3. Elements Registry Validation & Number Grounding
        from utils.vietnamese_accent import restore_known_accents
        for e_idx, el in enumerate(v_scene.elements):
            # Restore Vietnamese accents on content fields
            if el.content:
                for k in ("title", "text", "label", "unit"):
                    if el.content.get(k) and isinstance(el.content[k], str):
                        el.content[k] = restore_known_accents(el.content[k])
                if el.content.get("items") and isinstance(el.content["items"], list):
                    el.content["items"] = [restore_known_accents(str(itm)) for itm in el.content["items"]]
            # Registry check
            if not registry.is_registered(el.type):
                fallback = registry.find_fallback(el.type)
                msg = f"[element_registry, nhóm 2] Cảnh {sc_id}: phần tử '{el.type}' chưa hỗ trợ, tự động thay bằng '{fallback}'."
                notes.append(msg)
                v_scene.repair_notes.append(msg)
                el.type = fallback

            # Number Evidence Grounding
            has_numbers = False
            content = el.content or {}
            if any(k in content for k in ("value", "number_text", "bars", "percent")):
                has_numbers = True
            elif el.type in {"stat_number", "bar_compare", "gauge_ring", "container_fill"}:
                has_numbers = True

            if has_numbers and not el.no_numbers:
                evidence = (el.evidence or "").strip()
                norm_evidence = normalize_phrase_token(evidence)
                norm_script = normalize_phrase_token(scene_narration + " " + brief_facts_text)
                if not evidence or (norm_evidence and norm_evidence not in norm_script):
                    el.no_numbers = True
                    # Strip numeric values
                    if "value" in el.content:
                        el.content["value"] = None
                    msg = f"[number_grounding, nhóm 2] Cảnh {sc_id} phần tử {el.id}: không có bằng chứng (evidence) trong kịch bản; chuyển sang định tính (no_numbers=true)."
                    notes.append(msg)
                    v_scene.repair_notes.append(msg)

            # gauge_ring policy: CHỈ dùng cho phần trăm / tỉ lệ 0-100. Số tiền/số lượng -> tự đổi sang stat_number hoặc bar_compare
            if el.type in {"gauge_ring", "gauge", "ring"}:
                unit_str = str(content.get("unit") or content.get("unit_display") or "").strip()
                val_num = content.get("value")
                ev_str = str(el.evidence or "")
                is_pct = (unit_str == "%" or ("%" in ev_str and isinstance(val_num, (int, float)) and 0 <= val_num <= 100))
                if not is_pct:
                    old_type = el.type
                    new_type = "bar_compare" if content.get("bars") else "stat_number"
                    el.type = new_type
                    msg = f"[gauge_ring_policy, nhóm 2] Cảnh {sc_id} phần tử {el.id}: {old_type} chỉ dùng cho phần trăm (0-100); số liệu đơn vị '{unit_str or 'số'}' được tự động chuyển sang {new_type}."
                    notes.append(msg)
                    v_scene.repair_notes.append(msg)

            # Không bao giờ thêm "%" nếu evidence không chứa "%"
            if content.get("unit") == "%" and "%" not in (el.evidence or "") and "phần trăm" not in (el.evidence or "").lower():
                content["unit"] = ""
                msg = f"[unit_accuracy, nhóm 2] Cảnh {sc_id} phần tử {el.id}: gỡ bỏ nhầm '%' vì evidence không chứa phần trăm."
                notes.append(msg)
                v_scene.repair_notes.append(msg)

            # Timing matching for element enter
            at_sec, matched = match_at_phrase_to_seconds(
                el.enter.at_phrase,
                words,
                scene_duration,
                elem_idx=e_idx,
                total_elems=len(v_scene.elements),
            )
            el.enter.at_sec = at_sec
            if not matched and el.enter.at_phrase:
                msg = f"[timing_phrase, nhóm 2] Cảnh {sc_id}: cụm từ '{el.enter.at_phrase}' không khớp words.json; chia nhịp đều tại {at_sec:.2f}s."
                notes.append(msg)
                v_scene.repair_notes.append(msg)

            # Timing matching for element exit
            if el.exit.at_phrase in {"scene_end", ""}:
                el.exit.at_sec = scene_duration
            else:
                exit_sec, exit_matched = match_at_phrase_to_seconds(
                    el.exit.at_phrase,
                    words,
                    scene_duration,
                    elem_idx=e_idx + 1,
                    total_elems=len(v_scene.elements),
                )
                el.exit.at_sec = exit_sec

        # 4. Annotations Validation
        for a_idx, an in enumerate(v_scene.annotations):
            # Semantic check for strike vs check
            text_norm = (an.text or "").lower()
            if an.type == "strike":
                if re.search(r"\b(chính xác|đúng|xác nhận|thành công|tăng trưởng|chuẩn)\b", text_norm) and not re.search(
                    r"\b(không|sai|cũ|thay vì|lỗi|thất bại)\b", text_norm
                ):
                    an.type = "check"
                    msg = f"[annotation_semantics, nhóm 2] Cảnh {sc_id}: chú thích strike dùng trên nội dung khẳng định; chuyển sang 'check'."
                    notes.append(msg)
                    v_scene.repair_notes.append(msg)
            elif an.type == "check":
                if re.search(r"\b(sai|lỗi|thất bại|cũ|hỏng|nguy hiểm)\b", text_norm):
                    an.type = "cross"
                    msg = f"[annotation_semantics, nhóm 2] Cảnh {sc_id}: chú thích check dùng trên nội dung lỗi/hỏng; chuyển sang 'cross'."
                    notes.append(msg)
                    v_scene.repair_notes.append(msg)

            # Timing matching for annotations
            at_sec, matched = match_at_phrase_to_seconds(
                an.at_phrase,
                words,
                scene_duration,
                elem_idx=a_idx,
                total_elems=max(1, len(v_scene.annotations)),
            )
            an.at_sec = at_sec
            if not matched and an.at_phrase:
                msg = f"[timing_phrase, nhóm 2] Cảnh {sc_id}: chú thích '{an.at_phrase}' không khớp words.json; chia nhịp đều tại {at_sec:.2f}s."
                notes.append(msg)
                v_scene.repair_notes.append(msg)

        # 5. Mascot and SFX timing
        if v_scene.mascot and v_scene.mascot.at_phrase:
            m_sec, m_matched = match_at_phrase_to_seconds(
                v_scene.mascot.at_phrase, words, scene_duration, elem_idx=0, total_elems=1
            )
            v_scene.mascot.at_sec = m_sec

        for sf in v_scene.sfx:
            if sf.at_phrase:
                s_sec, _ = match_at_phrase_to_seconds(sf.at_phrase, words, scene_duration, elem_idx=0, total_elems=1)
                sf.at_sec = s_sec

    visual_resp.repair_notes = list(dict.fromkeys(notes))
    return visual_resp, notes


def map_visual_scene_to_motion_scene_plan(
    v_scene: VisualScene,
    duration_sec: float,
    central_metaphor: str = "",
    theme: str = "neon_dark",
    anchor: str = "",
    metaphor_state: str = "",
) -> MotionScenePlan:
    """Map a VisualScene (v3) to the unified MotionScenePlan contract."""
    primary_elem = v_scene.elements[0] if v_scene.elements else None
    scene_type_map = {
        "container_fill": "container_fill",
        "bar_compare": "bar_compare",
        "stat_number": "stat_number",
        "flow_chain": "flow_chain",
        "steps_ladder": "stack_cards",
        "gauge_ring": "gauge_ring",
    }
    valid_scene_types = set(get_args(SceneType))

    if primary_elem and primary_elem.type in valid_scene_types:
        stype = primary_elem.type
    elif primary_elem:
        stype = scene_type_map.get(primary_elem.type, "text_focus")
    else:
        stype = "text_focus"

    # Assemble VisualData
    data = VisualData()
    data.title = v_scene.section_title
    if primary_elem:
        c = primary_elem.content or {}
        data.text = str(c.get("text") or c.get("label") or v_scene.section_title or "")
        data.value = c.get("value")
        data.unit = str(c.get("unit") or "")
        data.number_text = str(c.get("number_text") or (str(data.value) if data.value is not None else ""))
        if "bars" in c and isinstance(c["bars"], list):
            data.bars = [
                VisualBar(label=str(b.get("label", "")), value=float(b.get("value", 0.0)), unit=str(b.get("unit", "")))
                for b in c["bars"]
                if isinstance(b, dict) and math.isfinite(float(b.get("value", 0.0)))
            ]
        if "items" in c and isinstance(c["items"], list):
            from agents.presentation import clean_semantic_label, labels_are_duplicate
            cleaned_items = []
            for it in c["items"]:
                s_it = str(it).strip()
                if not s_it:
                    continue
                cl = clean_semantic_label(s_it) or s_it
                if not any(labels_are_duplicate(cl, exist) for exist in cleaned_items):
                    cleaned_items.append(cl)
            data.items = cleaned_items

    # Assemble beats
    beats: list[VisualBeat] = []
    for el in v_scene.elements:
        beats.append(
            VisualBeat(
                at_sec=el.enter.at_sec if el.enter.at_sec is not None else 0.5,
                action=f"element_{el.id}_{el.enter.anim}",
            )
        )
    for an in v_scene.annotations:
        beats.append(
            VisualBeat(
                at_sec=an.at_sec if an.at_sec is not None else 1.0,
                action=f"annot_{an.type}_{an.target}",
            )
        )
    beats.sort(key=lambda b: b.at_sec)

    mascot_state = v_scene.mascot.state if v_scene.mascot else "idle"

    return MotionScenePlan(
        scene_type=stype,  # type: ignore
        theme=theme,  # type: ignore
        layout=v_scene.layout,  # type: ignore
        zone=primary_elem.zone if primary_elem else "center",  # type: ignore
        evidence=primary_elem.evidence if primary_elem else "",
        no_numbers=primary_elem.no_numbers if primary_elem else False,
        anchor=anchor or (primary_elem.id if primary_elem else None),
        central_metaphor=central_metaphor,
        metaphor_state=metaphor_state,
        data=data,
        beats=beats,
        camera=v_scene.camera,
        mascot_state=mascot_state,  # type: ignore
        annotations=[an.model_dump(mode="json") for an in v_scene.annotations],
        repair_notes=list(dict.fromkeys(v_scene.repair_notes)),
    )


def create_visual_plan_v3(
    plan: EditPlan,
    words_by_scene: dict[int, list[dict[str, Any]]] | None = None,
    brief: ResearchBrief | None = None,
    provider: Any = None,
    settings: Settings | None = None,
    diagnostics: Diagnostics | None = None,
    progress: Callable[[str], None] | None = None,
    state_path: Path | None = None,
) -> EditPlan:
    """
    Execute Visual Planner Prompt B: generate rich motion visual plans,
    validate with Pydantic, resolve timings against words.json, and bind to EditPlan.
    """
    from providers.llm.router import Router

    cfg = settings or Settings()
    step_provider = provider or Router(cfg, step="visual")

    if progress:
        progress("Đang đọc mẫu prompt visual_planner.md...")

    prompt_path = find_prompt_path("visual_planner.md", cfg)
    template_text = prompt_path.read_text(encoding="utf-8")
    rendered_prompt = render_visual_prompt(template_text, plan, brief, REGISTRY)

    if progress:
        progress("Đang gọi LLM Visual Planner qua router...")

    raw_response: str = ""
    parsed_json: dict[str, Any] = {}
    max_retries = 2

    for attempt in range(max_retries + 1):
        try:
            call_prompt = rendered_prompt
            if attempt > 0:
                call_prompt += (
                    f"\n\nLƯU Ý LẦN THỬ {attempt+1}: Kết quả trước không parse được JSON hợp lệ. "
                    "Hãy chỉ trả về duy nhất khối JSON thuần, không bọc markdown giải thích."
                )
            if hasattr(step_provider, "generate_json"):
                res = step_provider.generate_json(call_prompt)
                parsed_json = res if isinstance(res, dict) else json.loads(str(res))
            elif hasattr(step_provider, "generate"):
                raw_response = step_provider.generate(call_prompt)
                match = re.search(r"\{[\s\S]*\}", raw_response)
                if not match:
                    raise ValueError("Không tìm thấy khối JSON trong phản hồi của Visual Planner.")
                parsed_json = json.loads(match.group(0))
            elif hasattr(step_provider, "generate_text"):
                raw_response = step_provider.generate_text(call_prompt)
                match = re.search(r"\{[\s\S]*\}", raw_response)
                if not match:
                    raise ValueError("Không tìm thấy khối JSON trong phản hồi của Visual Planner.")
                parsed_json = json.loads(match.group(0))
            break
        except Exception as exc:
            _log_director_error(f"Lần gọi {attempt+1} thất bại: {exc}", exc, diagnostics)
            if attempt == max_retries:
                # Fallback to default visual plan for each scene
                if progress:
                    progress("LLM visual planner không trả về JSON hợp lệ; áp dụng kế hoạch hoạt họa mặc định.")
                parsed_json = {
                    "theme": "neon_dark",
                    "central_metaphor": {"name": "Hệ thống chịu tải", "anchor_element": "cỗ máy"},
                    "scenes": [
                        {
                            "scene_id": sc.id,
                            "purpose": getattr(sc, "role", "explain"),
                            "section_title": sc.narration[:20],
                            "layout": "center_hero",
                            "elements": [{"id": f"e{sc.id}_1", "type": "stat_number", "zone": "center"}],
                        }
                        for sc in plan.scenes
                    ],
                }

    # Pre-validation normalization
    normalized_data = normalize_visual_v3_payload(parsed_json)
    visual_resp = VisualPlanResponse.model_validate(normalized_data)

    # Resolve words_by_scene if not supplied directly
    resolved_words = dict(words_by_scene or {})
    for sc in plan.scenes:
        if sc.id not in resolved_words:
            # Check audio sidecar if available
            audio_words: list[dict[str, Any]] = []
            if hasattr(sc, "audio") and sc.audio:
                audio_path = Path(sc.audio)
                sidecar = audio_path.with_suffix(".words.json")
                if sidecar.is_file():
                    audio_words = read_words(sidecar)
            if not audio_words:
                dur = getattr(sc, "duration_sec", 0.0) or 8.0
                audio_words = estimate_words(sc.narration, dur)
            resolved_words[sc.id] = audio_words

    # Verification and self-repair
    if progress:
        progress("Đang kiểm tra và tự sửa ràng buộc kế hoạch hình ảnh...")

    repaired_resp, validation_notes = validate_and_repair_visual_plan(
        visual_resp,
        plan,
        brief,
        words_by_scene=resolved_words,
        registry=REGISTRY,
    )

    # Publish notes to plan review_notes
    for note in validation_notes:
        if note not in plan.review_notes:
            plan.review_notes.append(note)
            if diagnostics:
                try:
                    diagnostics.record(note)
                except OSError:
                    pass

    # Map scenes into MotionScenePlan
    metaphor_name = repaired_resp.central_metaphor.name or "Hệ thống"
    anchor_elem = repaired_resp.central_metaphor.anchor_element or ""
    # Topic matching for illustration anchor if generic or empty
    if not anchor_elem or anchor_elem in {"cỗ máy", "hệ thống", "thiết bị", "mô hình", ""}:
        matched_ill = None
        if brief:
            matched_ill = match_illustration_for_topic(f"{brief.topic or ''} {brief.summary or ''}")
        if not matched_ill:
            full_script = " ".join(s.narration for s in plan.scenes)
            matched_ill = match_illustration_for_topic(full_script)
        if matched_ill:
            anchor_elem = matched_ill
        else:
            anchor_elem = "drone"
    theme_name = repaired_resp.theme or "neon_dark"
    states_by_scene = repaired_resp.central_metaphor.states_by_scene or {}
    scenes_by_id = {sc.scene_id: sc for sc in repaired_resp.scenes}

    for sc_idx, scene in enumerate(plan.scenes):
        v_scene = scenes_by_id.get(scene.id) or (repaired_resp.scenes[sc_idx] if sc_idx < len(repaired_resp.scenes) else None)
        dur = getattr(scene, "duration_sec", 0.0) or 8.0
        m_state = states_by_scene.get(str(scene.id), states_by_scene.get(str(sc_idx + 1), ""))
        if v_scene:
            try:
                motion_plan = map_visual_scene_to_motion_scene_plan(
                    v_scene,
                    dur,
                    central_metaphor=metaphor_name,
                    theme=theme_name,
                    anchor=anchor_elem,
                    metaphor_state=m_state,
                )
                scene.visual_plan = motion_plan
            except Exception as exc:
                _log_director_error(f"Cảnh {scene.id}: lỗi map MotionScenePlan ({exc}); fallback text_focus", exc, diagnostics)
                scene.visual_plan = MotionScenePlan(
                    scene_type="text_focus",
                    repair_notes=[f"[visual_error, nhóm 2] Lỗi tạo visual_plan cảnh {scene.id}; dùng text_focus."],
                )
        else:
            scene.visual_plan = MotionScenePlan(scene_type="text_focus")

    # Ensure at least one scene has a valid visual_plan
    if not any(s.visual_plan is not None for s in plan.scenes):
        raise RuntimeError("[visual_planner, nhóm 1] Không dựng nổi bất kỳ cảnh nào trong kế hoạch hoạt họa.")

    # Save atomic checkpoint
    checkpoint_path = state_path or (cfg.root_dir / "director_state.visual_v3.json")
    try:
        write_json_atomic(
            checkpoint_path,
            {
                "visual_plan_v3": repaired_resp.model_dump(mode="json"),
                "review_notes": plan.review_notes,
            },
        )
    except Exception as exc:
        _log_director_error(f"Không thể lưu checkpoint visual_v3: {exc}", exc, diagnostics)

    if progress:
        progress("Hoàn thành lập kế hoạch hình ảnh hoạt họa Visual Planner v3.")

    return plan
