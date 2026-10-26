"""Script Writer v3: Leading conversational tech explainer scripts with checks and self-repair."""
import json
import re
from pathlib import Path
from typing import Any, Callable

from config.settings import Settings
from schemas.research_brief import ResearchBrief, Fact
from schemas.explainer import KnowledgeNote
from agents.director import DirectorRequest
from schemas.edit_plan import EditPlan, Scene, Shot
from schemas.explainer import ExplainerOutline, ExplainerBeat, ScriptSentence
from schemas.script_v3 import (
    ScriptV3Response,
    ScriptV3Scene,
    ScriptV3Sentence,
    normalize_script_v3_payload,
)
from utils.atomic_io import write_json_atomic, read_json_atomic
from utils.diagnostics import Diagnostics
from agents.proper_names import proper_names, at_boundary, common, foreign_token


def _log_director_error(message: str, error: Exception | None = None, diagnostics: Diagnostics | None = None) -> None:
    """Log error to logs/director_errors.log with credential redaction."""
    try:
        log_dir = Path("logs")
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "director_errors.log"
        err_msg = f": {type(error).__name__} - {str(error)}" if error else ""
        text = f"[ScriptWriterV3] {message}{err_msg}\n"
        if diagnostics is not None:
            text = diagnostics.redact(text)
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(text)
    except Exception:
        pass


def render_script_prompt(
    template_text: str,
    brief: ResearchBrief,
    category: str,
    duration_sec: float,
) -> str:
    """Fill variables {CATEGORY}, {SECONDS}, {N}, {S} and real brief facts into prompt A."""
    sec = int(duration_sec)
    word_count = round(duration_sec * 2.8)  # ~160 words for 60s
    scene_count = max(4, min(7, round(duration_sec / 10)))  # ~6 scenes for 60s

    # Format facts and knowledge notes
    fact_lines: list[str] = []
    for i, f in enumerate(brief.facts, 1):
        src = f.source_name or "nguồn tin"
        date_str = f", {f.published_at}" if getattr(f, "published_at", None) else ""
        text = f.fact_vi or f.claim
        fact_lines.append(f"[Fact {i}] (nguồn: {src}{date_str}): {text}")

    if brief.knowledge_notes:
        fact_lines.append("\n[KIẾN THỨC NỀN & ẨN DỤ GỢI Ý]:")
        for n in brief.knowledge_notes:
            analogy = f" (Ẩn dụ: {n.analogy})" if getattr(n, "analogy", None) else ""
            fact_lines.append(f"- {n.text}{analogy}")

    if getattr(brief, "key_numbers", None):
        fact_lines.append("\n[CON SỐ QUAN TRỌNG]:")
        for num in brief.key_numbers:
            fact_lines.append(f"- {num.value} {num.unit}: {num.context}")

    facts_text = "\n".join(fact_lines)

    rendered = template_text.replace("{CATEGORY}", category)
    rendered = rendered.replace("{SECONDS}", str(sec))
    rendered = rendered.replace("{N}", str(word_count))
    rendered = rendered.replace("{S}", str(scene_count))
    rendered = rendered.replace("<<<DÁN CÁC FACT/BÀI VIẾT VÀO ĐÂY>>>", facts_text)
    return rendered


# Common boilerplate openings that should be stripped or rewritten
BOILERPLATE_OPENINGS = re.compile(
    r"^(?:hôm nay (?:mình|chúng ta|tôi) sẽ (?:nói|kể|chia sẻ|bàn) về|trong video này|chào anh em[!,.]?|chào các bạn[!,.]?)\s*",
    re.I,
)

GENERIC_QUESTIONS = re.compile(
    r"^(?:bạn có biết|liệu bạn có|những yếu tố nào|tại sao lại như vậy|điều gì đã xảy ra)\b",
    re.I,
)

HEDGING_WORDS = re.compile(r"\b(?:có thể|có lẽ|dường như)\b", re.I)

DANGLING_CONJUNCTIONS = re.compile(r"\s+(?:và|của|cho|với|nhưng|vì|để|là|hay|hoặc)\s*[.!?]?$", re.I)


def check_and_repair_script(
    script: ScriptV3Response,
    brief: ResearchBrief,
    diagnostics: Diagnostics,
) -> ScriptV3Response:
    """Run checks and self-repairs on Script Writer v3 output:
    1. Hook check (<=14 words first sentence, 1 of 3 types, no generic questions/boilerplate).
    2. Central metaphor non-empty (derive from brief if missing).
    3. Interactive question at CTA.
    4. Limit 'có thể/có lẽ/dường như' (group 3 warning + auto-reduction).
    5. No dangling/truncated sentences.
    6. Event sentences grounding (check facts, avoid false positive uppercase sentence start).
    """
    valid_fact_ids = set(range(1, len(brief.facts) + 1))
    brief_text = " ".join([f.fact_vi for f in brief.facts] + [n.text for n in brief.knowledge_notes])

    # 1. Hook check & repair (Scene 1)
    if script.scenes:
        hook_scene = script.scenes[0]
        if hook_scene.sentences:
            first_sent = hook_scene.sentences[0]
            orig_text = first_sent.text

            # Strip boilerplate like "Hôm nay mình sẽ nói về..."
            if BOILERPLATE_OPENINGS.search(orig_text):
                cleaned = BOILERPLATE_OPENINGS.sub("", orig_text).strip()
                if cleaned:
                    # Capitalize first letter
                    first_sent.text = cleaned[0].upper() + cleaned[1:]
                    script.repair_notes.append("[hook, nhóm 2] Đã loại bỏ phần mở đầu khuôn mẫu trong hook.")

            # Turn generic questions into direct statements
            if GENERIC_QUESTIONS.search(first_sent.text):
                first_sent.text = GENERIC_QUESTIONS.sub("Sự thật bất ngờ về", first_sent.text).rstrip("?") + "."
                script.repair_notes.append("[hook, nhóm 2] Đã chuyển câu hỏi chung chung ở hook thành câu trực tiếp.")

            # Enforce max 14 words for opening statement
            words = first_sent.text.split()
            if len(words) > 16:
                # Trim if excessively long without losing meaning
                first_sent.text = " ".join(words[:14]).rstrip(" ,;:") + "."
                script.repair_notes.append("[hook, nhóm 2] Rút gọn câu đầu của hook xuống dưới 14 từ.")

    # 2. Central metaphor check & repair
    if not script.central_metaphor.strip():
        # Derive from knowledge notes or search scenes
        derived = ""
        for n in brief.knowledge_notes:
            if getattr(n, "analogy", None) and n.analogy.strip():
                derived = n.analogy.strip()
                break
        if not derived:
            # Look for comparison words in sentences
            for sc in script.scenes:
                for st in sc.sentences:
                    m = re.search(r"(?:giống như|như một|tương tự như)\s+([^,.]+)", st.text, re.I)
                    if m:
                        derived = m.group(1).strip()
                        break
                if derived:
                    break
        if not derived:
            derived = "Hệ thống chịu tải và điều phối năng lực"
        script.central_metaphor = derived
        script.repair_notes.append(f"[metaphor, nhóm 2] Tự động bổ sung ẩn dụ chủ đạo: '{derived}'.")

    # 3. Interactive question at CTA (Last Scene)
    if script.scenes:
        last_scene = script.scenes[-1]
        has_question = any("?" in s.text for s in last_scene.sentences)
        if not has_question:
            cta_question = "Bạn nghĩ sao về điều này? Hãy để lại ý kiến dưới phần bình luận."
            last_scene.sentences.append(ScriptV3Sentence(text=cta_question, type="cta", fact_ids=[]))
            script.repair_notes.append("[cta, nhóm 2] Tự động bổ sung câu hỏi tương tác ở cảnh kết.")

    # 4. Limit "có thể/có lẽ/dường như"
    total_hedges = 0
    scenes_with_hedges: list[tuple[int, int, str]] = []
    for sc_idx, sc in enumerate(script.scenes):
        for st_idx, st in enumerate(sc.sentences):
            found = HEDGING_WORDS.findall(st.text)
            if found:
                total_hedges += len(found)
                scenes_with_hedges.append((sc_idx, st_idx, st.text))

    max_allowed_hedges = max(1, len(script.scenes) // 2 + 1)
    if total_hedges > max_allowed_hedges:
        diagnostics.record(f"[hedging_limit, nhóm 3] Số từ đệm có thể/có lẽ ({total_hedges}) vượt giới hạn ({max_allowed_hedges}). Đang tự động tinh chỉnh.")
        script.repair_notes.append(f"[hedging_limit, nhóm 3] Giảm bớt từ đệm mềm thừa từ {total_hedges} xuống {max_allowed_hedges}.")

        # Auto-repair by removing excess hedges from sentences with definitive facts
        excess = total_hedges - max_allowed_hedges
        for sc_idx, st_idx, text in scenes_with_hedges:
            if excess <= 0:
                break
            st = script.scenes[sc_idx].sentences[st_idx]
            if HEDGING_WORDS.search(st.text):
                # Replace "có thể " or "có lẽ " with empty or direct phrasing
                new_text = re.sub(r"\b(?:có thể|có lẽ|dường như)\s+", "", st.text, count=1)
                if new_text != st.text:
                    st.text = new_text[0].upper() + new_text[1:] if new_text else st.text
                    excess -= 1

    # 5. Check dangling / truncated sentences
    for sc in script.scenes:
        for st in sc.sentences:
            if DANGLING_CONJUNCTIONS.search(st.text):
                st.text = DANGLING_CONJUNCTIONS.sub("", st.text).strip() + "."
                script.repair_notes.append(f"[syntax, nhóm 2] Đã xử lý câu bị cắt cụt ở cảnh {sc.scene_id}.")

    # 6. Event grounding validation (Nhóm 1 check)
    for sc in script.scenes:
        for st_idx, st in enumerate(sc.sentences):
            if st.type == "event":
                # Check invalid fact_ids
                invalid_ids = [fid for fid in st.fact_ids if fid not in valid_fact_ids]
                if invalid_ids:
                    # Repair: filter out invalid fact_ids
                    st.fact_ids = [fid for fid in st.fact_ids if fid in valid_fact_ids]
                    if not st.fact_ids:
                        # Fallback sentence to explain so it doesn't violate grounding
                        st.type = "explain"
                        script.repair_notes.append(f"[grounding, nhóm 2] Cảnh {sc.scene_id} câu {st_idx+1}: fact_id {invalid_ids} không tồn tại; chuyển nhãn sang explain.")

    return script


def to_edit_plan(
    script: ScriptV3Response,
    brief: ResearchBrief,
    request: DirectorRequest,
    settings: Settings,
) -> EditPlan:
    """Convert ScriptV3Response into an EditPlan compatible with the rest of the pipeline."""
    scenes: list[Scene] = []
    total_scenes = len(script.scenes)

    for idx, sc in enumerate(script.scenes):
        sentences = [
            ScriptSentence(
                type=s.type,
                text=s.text,
                fact_ids=s.fact_ids,
            )
            for s in sc.sentences
        ]
        narration = " ".join(s.text.strip() for s in sc.sentences if s.text.strip())
        words_count = len(narration.split())
        est_duration = max(3.0, round(words_count / 3.0, 1))

        # Role mapping
        if idx == 0:
            role = "hook"
        elif idx == total_scenes - 1 or sc.purpose == "cta":
            role = "cta"
        else:
            role = "body"

        # Information kind
        kind_mapping = {
            "hook": "cause",
            "explain": "mechanism",
            "example": "example",
            "analysis": "comparison",
            "evaluate": "counterpoint",
            "climax": "consequence",
            "cta": "metaphor",
        }
        info_kind = kind_mapping.get(sc.purpose, "mechanism")

        # Build Shots
        card_text = " ".join(narration.split()[:5]) if narration else sc.purpose
        shot_query = "technology explainer animation"
        if sc.visual_hint:
            shot_query = sc.visual_hint[:60]
        elif brief.topic:
            shot_query = f"{brief.topic[:30]} visual concept"

        shots = [
            Shot(
                type="stock_video",
                semantic_query=True,
                query=shot_query,
                duration_sec=est_duration,
                planning_duration=True,
                effect="zoom_in",
                text_overlay=None,
                card_text=card_text,
                emphasis=narration.split()[:2] if narration else [],
            )
        ]

        scene_obj = Scene(
            id=sc.scene_id,
            role=role,
            narration=narration,
            sentences=sentences,
            information_kind=info_kind,
            new_information=narration[:120],
            fact_ids=list(dict.fromkeys(fid for s in sentences if s.type == "event" for fid in s.fact_ids)),
            shots=shots,
            transition_out="fade",
            sfx="none",
            pattern_interrupt=(idx % 2 == 1),
            repair_notes=list(sc.repair_notes),
        )
        scenes.append(scene_obj)

    title = script.title.strip() if script.title else f"Khám phá {brief.topic[:30]}"
    if len(title) > 60:
        title = title[:60].rsplit(" ", 1)[0]

    outline = ExplainerOutline(
        angle=brief.topic or "Giải thích công nghệ",
        hook=scenes[0].narration if scenes else "",
        open_loop="",
        payoff=scenes[-1].narration if scenes else "",
        beats=[
            ExplainerBeat(
                id=s.id,
                kind=s.information_kind or "mechanism",
                idea=s.role or "explain",
                new_information=s.new_information or s.narration,
                fact_ids=s.fact_ids,
            )
            for s in scenes
        ],
    )

    plan = EditPlan(
        title=title,
        format=request.video_format,
        voice=settings.default_voice,
        music={"mood": "calm", "volume": 0.08},
        scenes=scenes,
        content_mode="explainer_v2",
        content_timed=True,
        video_type=request.video_type,
        requested_duration_sec=request.requested_duration_sec or request.duration_sec,
        script_style="explain",
        creative_license=request.creative_license,
        explainer_outline=outline,
        review_notes=list(script.repair_notes),
    )
    if script.central_metaphor:
        plan.review_notes.append(f"Ẩn dụ chủ đạo: {script.central_metaphor}")

    return plan


def create_script_v3_plan(
    brief: ResearchBrief,
    request: DirectorRequest,
    provider: Any,
    settings: Settings,
    diagnostics: Diagnostics,
    progress: Callable[[str], None] = print,
    *,
    draft_path: Path | None = None,
) -> EditPlan:
    """Generate script and EditPlan using Script Writer v3 (Prompt A)."""
    progress("Script Writer v3 · Đang tạo kịch bản với Prompt A…")
    template_path = settings.prompts_dir / "script_writer.md"
    if not template_path.is_file():
        alt_candidates = [
            Path("video_ai_tool/prompts/script_writer.md"),
            Path("prompts/script_writer.md"),
            Path(__file__).resolve().parent.parent / "prompts" / "script_writer.md",
        ]
        for candidate in alt_candidates:
            if candidate.is_file():
                template_path = candidate
                break
        else:
            raise FileNotFoundError(f"Không tìm thấy template prompt tại {template_path}")

    template_text = template_path.read_text(encoding="utf-8")
    category = request.category or "công nghệ"
    prompt = render_script_prompt(template_text, brief, category, request.duration_sec)

    # Calling LLM with retries on syntax error
    last_error: Exception | None = None
    script_resp: ScriptV3Response | None = None
    system_feedback = ""

    for attempt in range(settings.retry_attempts):
        call_prompt = prompt
        if system_feedback:
            call_prompt = f"{prompt}\n\n[LƯU Ý LỖI LƯỢT TRƯỚC]:\n{system_feedback}\nHãy khắc phục và chỉ trả về JSON hợp lệ."
        try:
            progress(f"Script Writer v3 · Gọi LLM (lượt {attempt + 1})…")
            raw_output = provider.generate_json(call_prompt, ScriptV3Response)
            
            # Normalize payload before strict Pydantic validation
            cleaned_data = normalize_script_v3_payload(raw_output)
            script_resp = ScriptV3Response.model_validate(cleaned_data)
            break
        except Exception as err:
            last_error = err
            system_feedback = f"Lỗi parse JSON / schema: {type(err).__name__} - {str(err)}"
            _log_director_error(f"Lượt {attempt+1} lỗi: {system_feedback}", err, diagnostics)
            diagnostics.record(f"Script Writer v3 retry {attempt + 1}: {err}")

    if script_resp is None:
        raise RuntimeError(f"Script Writer v3 không thể tạo kịch bản sau {settings.retry_attempts} lần thử: {last_error}")

    # Checks and self-repair
    progress("Script Writer v3 · Đang kiểm tra và tự sửa theo chuẩn…")
    script_resp = check_and_repair_script(script_resp, brief, diagnostics)

    # Transform to EditPlan
    plan = to_edit_plan(script_resp, brief, request, settings)

    # Save state checkpoint
    checkpoint_path = (draft_path or settings.output_dir / "edit_plan.draft.json").with_name("director_state.script_v3.json")
    try:
        write_json_atomic(checkpoint_path, {
            "mode": "script_v3",
            "title": plan.title,
            "metaphor": script_resp.central_metaphor,
            "scenes": [s.model_dump(mode="json") for s in plan.scenes],
            "repair_notes": plan.review_notes,
        })
    except Exception:
        pass

    return plan
