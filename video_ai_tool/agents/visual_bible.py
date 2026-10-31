"""Visual Bible Agent (Giai đoạn 8-W2a).
Tạo và kiểm định Visual Bible (Kế hoạch hình ảnh tổng thể xuyên suốt video):
- Thế giới isometric (worlds)
- Vật thể xuyên suốt (persistent_actors)
- Cấu trúc chương (chapters, 'PHẦN i/N')
- Ẩn dụ tiến độ (progress_metaphor)
- Ánh xạ khái niệm trực quan có bằng chứng (concepts)
- Danh mục số liệu cho phép (numbers_allowed)
"""
import datetime
import json
import logging
import re
import unicodedata
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import yaml

from config.settings import Settings, get_settings
from schemas.edit_plan import EditPlan
from schemas.research_brief import ResearchBrief
from schemas.visual_bible import (
    ALLOWED_ACTOR_TYPES,
    ALLOWED_WORLD_KINDS,
    ChapterDef,
    ConceptDef,
    PersistentActorDef,
    ProgressMetaphorDef,
    StructureDef,
    VisualBible,
    VisualBibleStatus,
    WorldDef,
)
from utils.atomic_io import read_json_atomic, write_json_atomic
from utils.diagnostics import Diagnostics

logger = logging.getLogger(__name__)


def _normalize_text(text: str) -> str:
    norm = unicodedata.normalize("NFD", str(text).casefold())
    norm = "".join(c for c in norm if not unicodedata.combining(c))
    norm = norm.replace("đ", "d")
    return "".join(c for c in norm if c.isalnum() or c.isspace())


def load_theme_palette(theme_name: str = "neon_dark") -> Dict[str, str]:
    """Load color palette from config/motion_theme.yaml or config/themes.yaml."""
    cfg_file = Path("config/motion_theme.yaml")
    if not cfg_file.is_file():
        cfg_file = Path(__file__).resolve().parent.parent / "config" / "motion_theme.yaml"
    if cfg_file.is_file():
        try:
            data = yaml.safe_load(cfg_file.read_text(encoding="utf-8"))
            themes = data.get("themes", {})
            if theme_name in themes:
                return {k: str(v) for k, v in themes[theme_name].items()}
        except Exception as exc:
            logger.warning("Failed to load motion_theme.yaml: %s", exc)

    # Fallback default palette
    return {
        "top": "#0a0e1c",
        "bottom": "#05070f",
        "card": "#12192e",
        "foreground": "#f4f7ff",
        "accent": "#00f0ff",
        "secondary": "#ff007f",
    }


def extract_allowed_numbers(text_corpus: str) -> List[Union[int, float]]:
    """Extract numeric values grounded in spoken text / brief."""
    numbers: List[Union[int, float]] = []
    # Match integer and decimal numbers
    matches = re.findall(r"\b\d+(?:[.,]\d+)?\b", text_corpus)
    for m in matches:
        clean_num = m.replace(",", ".")
        try:
            val = float(clean_num)
            val_out = int(val) if val.is_integer() else val
            if val_out not in numbers:
                numbers.append(val_out)
        except ValueError:
            pass
    return numbers


def validate_and_heal_visual_bible(
    bible_data: Dict[str, Any],
    edit_plan: EditPlan,
    brief: Optional[Union[ResearchBrief, Dict[str, Any]]] = None,
    diagnostics: Optional[Diagnostics] = None,
) -> Tuple[VisualBible, List[str]]:
    """
    Validator nhóm 2 (tự sửa) cho Visual Bible:
    - Worlds: kind hợp lệ, tối đa 2 thế giới.
    - Persistent actors: type thuộc catalog Stage DSL, tối đa 3 actors.
    - Chapters: title <= 5 từ, kicker 'PHẦN i/N'.
    - Concepts: term và evidence_sentence phải có trong lời đọc / brief; nếu không có thì loại bỏ.
    - Numbers allowed: chỉ giữ các số thực sự có trong lời đọc / brief.
    """
    notes: List[str] = []

    # Build corpus of script and brief for grounding checks
    script_sentences: List[str] = []
    for sc in edit_plan.scenes:
        if sc.narration:
            script_sentences.append(sc.narration)
            for part in re.split(r"[.!?…]+", sc.narration):
                p_str = part.strip()
                if len(p_str) > 5:
                    script_sentences.append(p_str)
        for sh in sc.shots:
            if sh.card_text:
                script_sentences.append(sh.card_text)

    brief_text = ""
    if brief:
        if isinstance(brief, dict):
            brief_text = brief.get("summary", "") or brief.get("topic", "") or ""
            facts = brief.get("facts", [])
            for f in facts:
                if isinstance(f, dict):
                    brief_text += " " + f.get("text", "")
                elif isinstance(f, str):
                    brief_text += " " + f
        elif hasattr(brief, "model_dump"):
            b_dict = brief.model_dump(mode="json")
            brief_text = b_dict.get("summary", "") or b_dict.get("topic", "") or ""
            for f in b_dict.get("facts", []):
                brief_text += " " + (f.get("text", "") if isinstance(f, dict) else str(f))

    full_corpus = " ".join(script_sentences) + " " + brief_text
    norm_corpus = _normalize_text(full_corpus)

    # 1. Worlds validation
    raw_worlds = bible_data.get("worlds", [])
    valid_worlds: List[WorldDef] = []
    for w in raw_worlds:
        w_dict = w if isinstance(w, dict) else (w.model_dump(mode="json") if hasattr(w, "model_dump") else {})
        w_kind = w_dict.get("kind", "generic_stage")
        if w_kind not in ALLOWED_WORLD_KINDS:
            notes.append(f"Visual Bible nhóm 2: World kind '{w_kind}' không hợp lệ, tự sửa thành 'generic_stage'.")
            w_kind = "generic_stage"
        zones = w_dict.get("zones", [])
        if not zones:
            zones = ["main_zone", "support_zone"]
        valid_worlds.append(
            WorldDef(
                id=str(w_dict.get("id", f"world_{len(valid_worlds)+1}")),
                kind=w_kind,
                reason=str(w_dict.get("reason", "Phù hợp với nội dung kịch bản.")),
                zones=[str(z) for z in zones],
            )
        )
    if len(valid_worlds) > 2:
        notes.append(f"Visual Bible nhóm 2: Số world {len(valid_worlds)} > 2, cắt gọn còn 2.")
        valid_worlds = valid_worlds[:2]
    elif len(valid_worlds) == 0:
        notes.append("Visual Bible nhóm 2: Thiếu world, tự bổ sung generic_stage.")
        valid_worlds.append(WorldDef(id="world_1", kind="generic_stage", reason="Sân khấu tổng quan.", zones=["zone_chinh", "zone_phu"]))

    # 2. Persistent Actors validation
    raw_actors = bible_data.get("persistent_actors", [])
    valid_actors: List[PersistentActorDef] = []
    for a in raw_actors:
        a_dict = a if isinstance(a, dict) else (a.model_dump(mode="json") if hasattr(a, "model_dump") else {})
        a_type = a_dict.get("type", "note_board")
        if a_type not in ALLOWED_ACTOR_TYPES:
            notes.append(f"Visual Bible nhóm 2: Actor type '{a_type}' ngoài catalog, tự sửa thành 'note_board'.")
            a_type = "note_board"
        states = a_dict.get("states", [])
        if not states:
            states = ["default", "active"]
        valid_actors.append(
            PersistentActorDef(
                id=str(a_dict.get("id", f"actor_{len(valid_actors)+1}")),
                type=a_type,
                role=str(a_dict.get("role", "Thực thể trực quan xuyên suốt")),
                states=[str(s) for s in states],
            )
        )
    if len(valid_actors) > 3:
        notes.append(f"Visual Bible nhóm 2: Số persistent actors {len(valid_actors)} > 3, cắt gọn còn 3.")
        valid_actors = valid_actors[:3]
    elif len(valid_actors) == 0:
        notes.append("Visual Bible nhóm 2: Thiếu persistent actor, tự bổ sung note_board.")
        valid_actors.append(PersistentActorDef(id="actor_1", type="note_board", role="Bảng thông tin trực quan", states=["default", "active"]))

    # 3. Structure & Chapters validation
    raw_struct = bible_data.get("structure", {})
    raw_chapters = raw_struct.get("chapters", []) if isinstance(raw_struct, dict) else []
    total_scenes = len(edit_plan.scenes)
    valid_chapters: List[ChapterDef] = []
    total_chaps = len(raw_chapters) if 1 <= len(raw_chapters) <= 4 else (3 if total_scenes >= 5 else 2)

    if raw_chapters:
        for idx, ch in enumerate(raw_chapters, 1):
            ch_dict = ch if isinstance(ch, dict) else (ch.model_dump(mode="json") if hasattr(ch, "model_dump") else {})
            raw_title = str(ch_dict.get("title", f"Chương {idx}")).strip()
            title_words = raw_title.split()
            if len(title_words) > 5:
                notes.append(f"Visual Bible nhóm 2: Tiêu đề chương '{raw_title}' vượt quá 5 từ, rút gọn còn 5 từ.")
                raw_title = " ".join(title_words[:5])
            kicker = f"PHẦN {idx}/{len(raw_chapters)}"
            sc_ids = ch_dict.get("scene_ids", [])
            valid_sc_ids = [sc.id for sc in edit_plan.scenes if sc.id in sc_ids or str(sc.id) in map(str, sc_ids)]
            if not valid_sc_ids:
                valid_sc_ids = [edit_plan.scenes[min(idx - 1, total_scenes - 1)].id]
            valid_chapters.append(
                ChapterDef(
                    id=ch_dict.get("id", f"chap_{idx}"),
                    title=raw_title,
                    scene_ids=valid_sc_ids,
                    kicker=kicker,
                )
            )
    else:
        # Generate default chapters covering all scenes
        notes.append("Visual Bible nhóm 2: Thiếu cấu trúc chương, tự phân bổ chapters theo số cảnh.")
        step_sz = max(1, total_scenes // total_chaps)
        for idx in range(total_chaps):
            start_i = idx * step_sz
            end_i = (idx + 1) * step_sz if idx < total_chaps - 1 else total_scenes
            sub_scenes = edit_plan.scenes[start_i:end_i]
            sc_ids = [sc.id for sc in sub_scenes]
            ch_title = sub_scenes[0].role.title() if sub_scenes else f"Phần {idx+1}"
            valid_chapters.append(
                ChapterDef(
                    id=f"chap_{idx+1}",
                    title=" ".join(ch_title.split()[:4]),
                    scene_ids=sc_ids,
                    kicker=f"PHẦN {idx+1}/{total_chaps}",
                )
            )

    # 4. Progress Metaphor validation
    raw_pm = bible_data.get("progress_metaphor", {})
    pm_dict = raw_pm if isinstance(raw_pm, dict) else (raw_pm.model_dump(mode="json") if hasattr(raw_pm, "model_dump") else {})
    pm_type = pm_dict.get("type", "step_bar")
    if pm_type not in {"none", "glass_fill", "step_bar", "stack_up"}:
        notes.append(f"Visual Bible nhóm 2: Progress metaphor '{pm_type}' không hợp lệ, chuyển về 'step_bar'.")
        pm_type = "step_bar"
    pm_items = pm_dict.get("items", [])
    if not pm_items:
        pm_items = [ch.title for ch in valid_chapters]
    valid_pm = ProgressMetaphorDef(type=pm_type, items=[str(it) for it in pm_items[:4]])

    # 5. Concepts Grounding Validation (Cấm bịa khái niệm và bằng chứng)
    raw_concepts = bible_data.get("concepts", [])
    valid_concepts: List[ConceptDef] = []
    for c in raw_concepts:
        c_dict = c if isinstance(c, dict) else (c.model_dump(mode="json") if hasattr(c, "model_dump") else {})
        term = str(c_dict.get("term", "")).strip()
        ev = str(c_dict.get("evidence_sentence", "")).strip()
        if not term:
            continue

        norm_term = _normalize_text(term)
        norm_ev = _normalize_text(ev)

        # Check if term or evidence appears in script or brief
        term_in_corpus = any(w in norm_corpus for w in norm_term.split() if len(w) >= 2)
        ev_in_corpus = norm_ev and (norm_ev in norm_corpus or any(s in norm_corpus for s in norm_ev.split(". ")))

        if not term_in_corpus and not ev_in_corpus:
            notes.append(f"Visual Bible nhóm 2: Loại bỏ khái niệm '{term}' vì không có trong lời đọc/brief.")
            continue

        # If evidence was inaccurate, find real sentence containing term
        if not ev_in_corpus:
            real_sentence = next((s for s in script_sentences if norm_term in _normalize_text(s)), script_sentences[0] if script_sentences else "")
            ev = real_sentence
            notes.append(f"Visual Bible nhóm 2: Tự sửa evidence_sentence cho '{term}' bám sát lời đọc thực tế.")

        valid_concepts.append(
            ConceptDef(
                term=term,
                scene_id=c_dict.get("scene_id", edit_plan.scenes[0].id),
                sentence_index=int(c_dict.get("sentence_index", 1)),
                world_zone=str(c_dict.get("world_zone", valid_worlds[0].zones[0])),
                actor_id=str(c_dict.get("actor_id", valid_actors[0].id)) if c_dict.get("actor_id") else None,
                evidence_sentence=ev,
            )
        )

    # 6. Numbers allowed verification
    corpus_numbers = extract_allowed_numbers(full_corpus)
    user_numbers = bible_data.get("numbers_allowed", [])
    valid_numbers = [n for n in user_numbers if n in corpus_numbers]
    for n in corpus_numbers:
        if n not in valid_numbers:
            valid_numbers.append(n)

    # Theme and palette
    theme_name = str(bible_data.get("theme_name", "neon_dark"))
    palette = bible_data.get("palette") or load_theme_palette(theme_name)

    visual_bible = VisualBible(
        theme_name=theme_name,
        palette=palette,
        worlds=valid_worlds,
        persistent_actors=valid_actors,
        structure=StructureDef(chapters=valid_chapters),
        progress_metaphor=valid_pm,
        concepts=valid_concepts,
        numbers_allowed=valid_numbers,
        notes=notes,
    )
    return visual_bible, notes


def generate_fallback_visual_bible(
    edit_plan: EditPlan,
    brief: Optional[Union[ResearchBrief, Dict[str, Any]]] = None,
    theme_name: str = "neon_dark",
) -> VisualBible:
    """Tạo Visual Bible dự phòng theo quy tắc (Rule-based Fallback) khi LLM lỗi."""
    full_text = " ".join(sc.narration for sc in edit_plan.scenes if sc.narration)
    norm = _normalize_text(full_text + " " + edit_plan.title)

    # 1. World selection based on domain keywords
    if any(k in norm for k in ["lo hong", "an ninh", "bao mat", "hack", "tan cong", "may chu", "php", "xac thuc", "firewall", "khai thac"]):
        world = WorldDef(
            id="world_secure_infra",
            kind="secure_building",
            reason="Minh họa hạ tầng máy chủ và hệ sinh thái bảo vệ dữ liệu mạng.",
            zones=["cong_kiem_soat", "phong_may_chu", "vung_khoa_bao_mat"],
        )
        actors = [
            PersistentActorDef(
                id="server_node",
                type="vps_server",
                role="Máy chủ dịch vụ trực tuyến cần bảo vệ",
                states=["normal", "busy", "alert"],
            ),
            PersistentActorDef(
                id="defense_shield",
                type="lock_shield",
                role="Hệ thống tường lửa và khóa an ninh mạng",
                states=["locked", "unlocked"],
            ),
        ]
        pm_type = "glass_fill" if any(k in norm for k in ["phan tram", "%", "ngan sach"]) else "step_bar"

    elif any(k in norm for k in ["toa an", "phien toa", "xet xu", "vu an", "cao trang", "toi danh", "cao buoc", "tham phan"]):
        world = WorldDef(
            id="world_court",
            kind="courtroom",
            reason="Không gian phân tích chứng cứ pháp lý và diễn biến tố tụng.",
            zones=["van_phong_luat", "phong_xet_xu", "khu_ho_so"],
        )
        actors = [
            PersistentActorDef(
                id="case_dossier",
                type="note_board",
                role="Bảng hồ sơ chứng cứ và các tình tiết vụ án",
                states=["evidence", "verdict"],
            )
        ]
        pm_type = "step_bar"

    elif any(k in norm for k in ["ai", "tri tue nhan tao", "model", "agent", "code", "lap trinh", "thuat toan"]):
        world = WorldDef(
            id="world_ai_lab",
            kind="lab",
            reason="Phòng thí nghiệm phát triển và vận hành các tác nhân trí tuệ nhân tạo.",
            zones=["khu_nghien_cuu", "cum_may_chu_ai", "man_hinh_giam_sat"],
        )
        actors = [
            PersistentActorDef(
                id="agent_console",
                type="terminal_window",
                role="Giao diện điều khiển AI agent",
                states=["typing", "active"],
            )
        ]
        pm_type = "step_bar"

    else:
        world = WorldDef(
            id="world_main_stage",
            kind="generic_stage",
            reason="Sân khấu trực quan isometric tổng quan cho chủ đề tin tức.",
            zones=["zone_chinh", "zone_so_sanh", "zone_tong_ket"],
        )
        actors = [
            PersistentActorDef(
                id="main_display",
                type="note_board",
                role="Bảng trình chiếu thông tin và số liệu",
                states=["default", "active"],
            )
        ]
        pm_type = "step_bar"

    # 2. Chapters structure
    total_scenes = len(edit_plan.scenes)
    num_chaps = 3 if total_scenes >= 5 else 2
    step_sz = max(1, total_scenes // num_chaps)
    chapters: List[ChapterDef] = []
    for idx in range(num_chaps):
        start_i = idx * step_sz
        end_i = (idx + 1) * step_sz if idx < num_chaps - 1 else total_scenes
        sub_sc = edit_plan.scenes[start_i:end_i]
        sc_ids = [s.id for s in sub_sc]
        title_raw = sub_sc[0].shots[0].card_text if (sub_sc and sub_sc[0].shots and sub_sc[0].shots[0].card_text) else (sub_sc[0].role.title() if sub_sc else f"Phần {idx+1}")
        title = " ".join(title_raw.split()[:4])
        chapters.append(
            ChapterDef(
                id=f"chap_{idx+1}",
                title=title,
                scene_ids=sc_ids,
                kicker=f"PHẦN {idx+1}/{num_chaps}",
            )
        )

    # 3. Concepts extracted from actual shot cards / narrations
    concepts: List[ConceptDef] = []
    for s_idx, sc in enumerate(edit_plan.scenes, 1):
        for sh_idx, sh in enumerate(sc.shots, 1):
            term = sh.card_text or (" ".join(sc.narration.split()[:3]) if sc.narration else f"Khái niệm {s_idx}")
            if len(concepts) < 6:
                concepts.append(
                    ConceptDef(
                        term=term,
                        scene_id=sc.id,
                        sentence_index=sh_idx,
                        world_zone=world.zones[sh_idx % len(world.zones)],
                        actor_id=actors[0].id,
                        evidence_sentence=sc.narration or term,
                    )
                )

    # 4. Numbers allowed
    numbers = extract_allowed_numbers(full_text)

    palette = load_theme_palette(theme_name)

    return VisualBible(
        theme_name=theme_name,
        palette=palette,
        worlds=[world],
        persistent_actors=actors,
        structure=StructureDef(chapters=chapters),
        progress_metaphor=ProgressMetaphorDef(type=pm_type, items=[ch.title for ch in chapters]),
        concepts=concepts,
        numbers_allowed=numbers,
        notes=["Tạo tự động bằng Fallback Rule-based của Visual Bible Agent."],
    )


def create_visual_bible(
    edit_plan: EditPlan,
    brief: Optional[Union[ResearchBrief, Dict[str, Any]]] = None,
    words_by_scene: Optional[Dict[Any, Any]] = None,
    settings: Optional[Settings] = None,
    provider: Any = None,
    diagnostics: Optional[Diagnostics] = None,
    progress: Optional[Callable[[str], None]] = None,
) -> Tuple[VisualBible, VisualBibleStatus]:
    """
    Sinh Visual Bible cho toàn bộ video:
    - Thử gọi LLM qua Router(settings, step="visual") với prompts/visual_bible.md.
    - Tự động chuyển fallback rule-based nếu LLM lỗi hoặc trả JSON không hợp lệ.
    - Áp dụng bộ kiểm định nhóm 2 loại bỏ dữ liệu sai lệch hoặc ungrounded.
    """
    cfg = settings or get_settings()
    theme_name = "neon_dark"
    if (Path("config/motion_theme.yaml")).is_file():
        theme_name = getattr(cfg, "motion_theme", "neon_dark")

    # Render prompt
    prompt_file = Path("prompts/visual_bible.md")
    if not prompt_file.is_file():
        prompt_file = Path(__file__).resolve().parent.parent / "prompts" / "visual_bible.md"

    prompt_tpl = prompt_file.read_text(encoding="utf-8") if prompt_file.is_file() else ""

    # Prepare context strings
    scenes_text_lines = []
    for sc in edit_plan.scenes:
        scenes_text_lines.append(f"Cảnh {sc.id} ({sc.role}): {sc.narration}")
        for sh in sc.shots:
            if sh.card_text:
                scenes_text_lines.append(f"  - Shot card: {sh.card_text}")
    scenes_text = "\n".join(scenes_text_lines)

    brief_summary = ""
    if brief:
        if isinstance(brief, dict):
            brief_summary = brief.get("summary", "") or brief.get("topic", "")
        elif hasattr(brief, "summary"):
            brief_summary = getattr(brief, "summary", "") or getattr(brief, "topic", "")

    rendered_prompt = (
        prompt_tpl.replace("{TITLE}", edit_plan.title or "Video Explainer")
        .replace("{BRIEF_SUMMARY}", brief_summary or "Chủ đề video")
        .replace("{SCENE_COUNT}", str(len(edit_plan.scenes)))
        .replace("{SCENES_TEXT}", scenes_text)
    )

    llm_ok = False
    fallback_used = False
    reason = ""
    parsed_json: Dict[str, Any] = {}

    if progress:
        progress("Đang khởi tạo Visual Bible cho video...")

    # Call LLM via Router if provider available or configured
    if provider is not None or getattr(cfg, "gemini_api_key", None) or getattr(cfg, "openai_api_key", None):
        step_provider = provider
        if step_provider is None:
            try:
                from providers.llm.router import Router
                step_provider = Router(cfg, step="visual", diagnostics=diagnostics)
            except Exception as exc:
                logger.warning("Router setup failed for visual bible: %s", exc)
                step_provider = None

        if step_provider is not None:
            try:
                if progress:
                    progress("Đang gọi LLM Visual Bible qua Router...")
                if hasattr(step_provider, "generate_json"):
                    res = step_provider.generate_json(rendered_prompt)
                    parsed_json = res if isinstance(res, dict) else json.loads(str(res))
                elif hasattr(step_provider, "generate_text"):
                    raw = step_provider.generate_text(rendered_prompt)
                    match = re.search(r"\{[\s\S]*\}", raw)
                    if not match:
                        raise ValueError("Không tìm thấy khối JSON trong phản hồi LLM.")
                    parsed_json = json.loads(match.group(0))
                elif hasattr(step_provider, "generate"):
                    raw = step_provider.generate(rendered_prompt)
                    match = re.search(r"\{[\s\S]*\}", raw)
                    if not match:
                        raise ValueError("Không tìm thấy khối JSON trong phản hồi LLM.")
                    parsed_json = json.loads(match.group(0))
                llm_ok = True
                reason = "LLM sinh Visual Bible thành công."
            except Exception as exc:
                logger.warning("LLM call for visual bible failed: %s; using rule-based fallback.", exc)
                reason = f"Lỗi LLM: {exc}"
                llm_ok = False
                fallback_used = True

    if not llm_ok or not parsed_json:
        fallback_used = True
        if not reason:
            reason = "Chưa cấu hình API Key hoặc LLM offline; sử dụng fallback rule-based."
        bible = generate_fallback_visual_bible(edit_plan, brief, theme_name=theme_name)
    else:
        # Validate and heal LLM output
        bible, repair_notes = validate_and_heal_visual_bible(parsed_json, edit_plan, brief, diagnostics=diagnostics)
        if repair_notes:
            reason += " (Đã áp dụng các sửa chữa nhóm 2: " + "; ".join(repair_notes) + ")"

    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    status = VisualBibleStatus(
        llm_ok=llm_ok,
        fallback_used=fallback_used,
        reason=reason,
        timestamp=now_iso,
    )

    return bible, status


def save_visual_bible(project_dir: Path, bible: VisualBible, status: VisualBibleStatus) -> None:
    """Ghi visual_bible.json và visual_bible_status.json vào thư mục dự án một cách an toàn."""
    bible_file = project_dir / "visual_bible.json"
    status_file = project_dir / "visual_bible_status.json"

    write_json_atomic(bible_file, bible.model_dump(mode="json"))
    write_json_atomic(status_file, status.model_dump(mode="json"))
    logger.info("Saved visual_bible.json and visual_bible_status.json to %s", project_dir)
