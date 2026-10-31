"""Anti-Repetition Scheduler & Metaphor-First Planner for Motion Vocabulary Recipes.
Enforces diverse visual metaphors, forbids consecutive repetitions, guarantees >=6 distinct recipes,
ensures >=3 visual beats per scene, and eliminates stillness intervals > 2.5s.
"""
from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class MotionFamily(str, Enum):
    NUMBER_STAT = "number_stat"
    FILL_LEVEL = "fill_level"
    COMPARE_VS = "compare_vs"
    PROCESS_FLOW = "process_flow"
    RISK_PROB = "risk_prob"
    CONCEPT_RELATION = "concept_relation"
    MOCK_UI = "mock_ui"


# Recipe to Family Mapping (28 Recipes + legacy elements)
RECIPE_FAMILY_MAP: Dict[str, MotionFamily] = {
    # Phase A Number Stat
    "slot_counter": MotionFamily.NUMBER_STAT,
    "strike_replace": MotionFamily.NUMBER_STAT,
    "gauge_needle": MotionFamily.NUMBER_STAT,
    "odometer": MotionFamily.NUMBER_STAT,
    "bar_race": MotionFamily.NUMBER_STAT,
    "thermometer": MotionFamily.NUMBER_STAT,
    "stat_number": MotionFamily.NUMBER_STAT,
    "numeric": MotionFamily.NUMBER_STAT,
    # Fill Level
    "battery_fill": MotionFamily.FILL_LEVEL,
    "glass_fill": MotionFamily.FILL_LEVEL,
    "container_fill": MotionFamily.FILL_LEVEL,
    "gauge_ring": MotionFamily.FILL_LEVEL,
    # Phase B Compare
    "balance_scale": MotionFamily.COMPARE_VS,
    "tug_of_war": MotionFamily.COMPARE_VS,
    "vs_flip_cards": MotionFamily.COMPARE_VS,
    "before_after_wipe": MotionFamily.COMPARE_VS,
    "versus_split": MotionFamily.COMPARE_VS,
    "versus_scale": MotionFamily.COMPARE_VS,
    "bar_compare": MotionFamily.COMPARE_VS,
    "bar_grow": MotionFamily.COMPARE_VS,
    # Phase B Process
    "conveyor_belt": MotionFamily.PROCESS_FLOW,
    "domino_chain": MotionFamily.PROCESS_FLOW,
    "funnel_filter": MotionFamily.PROCESS_FLOW,
    "pipeline_pipes": MotionFamily.PROCESS_FLOW,
    "flow_chain": MotionFamily.PROCESS_FLOW,
    # Phase B Risk
    "dice_roll": MotionFamily.RISK_PROB,
    "lock_unlock": MotionFamily.RISK_PROB,
    "shield_hit": MotionFamily.RISK_PROB,
    "traffic_light": MotionFamily.RISK_PROB,
    # Phase C Concept
    "orbit_system": MotionFamily.CONCEPT_RELATION,
    "layered_onion": MotionFamily.CONCEPT_RELATION,
    "stack_pile": MotionFamily.CONCEPT_RELATION,
    "puzzle_snap": MotionFamily.CONCEPT_RELATION,
    "steps_ladder": MotionFamily.CONCEPT_RELATION,
    "stack_cards": MotionFamily.CONCEPT_RELATION,
    "hub_spoke": MotionFamily.CONCEPT_RELATION,
    "network_nodes": MotionFamily.CONCEPT_RELATION,
    # Phase C Mock UI
    "chat_thread": MotionFamily.MOCK_UI,
    "mock_card_swipe": MotionFamily.MOCK_UI,
    "form_fill_submit": MotionFamily.MOCK_UI,
    "terminal_command_run": MotionFamily.MOCK_UI,
    "terminal_typing": MotionFamily.MOCK_UI,
    "code_card": MotionFamily.MOCK_UI,
    "mock_ui_window": MotionFamily.MOCK_UI,
    "checklist": MotionFamily.MOCK_UI,
    "magnifier_check": MotionFamily.MOCK_UI,
    # 12 New Recipes
    "before_after_split": MotionFamily.COMPARE_VS,
    "courtroom_balance": MotionFamily.COMPARE_VS,
    "timeline_milestones": MotionFamily.PROCESS_FLOW,
    "map_location_pin": MotionFamily.CONCEPT_RELATION,
    "profile_dossier": MotionFamily.MOCK_UI,
    "document_page_flip": MotionFamily.MOCK_UI,
    "camera_surveillance_scan": MotionFamily.RISK_PROB,
    "evidence_board": MotionFamily.CONCEPT_RELATION,
    "network_graph": MotionFamily.CONCEPT_RELATION,
    "countdown_timer": MotionFamily.NUMBER_STAT,
    "code_terminal_window": MotionFamily.MOCK_UI,
    "quote_dialog_card": MotionFamily.MOCK_UI,
}

# Cross-Family Equivalence Map for Auto-Repair
FAMILY_ALTERNATIVES: Dict[MotionFamily, List[str]] = {
    MotionFamily.NUMBER_STAT: ["slot_counter", "odometer", "strike_replace", "thermometer", "bar_race", "gauge_needle"],
    MotionFamily.FILL_LEVEL: ["battery_fill", "glass_fill", "container_fill", "gauge_ring"],
    MotionFamily.COMPARE_VS: ["balance_scale", "vs_flip_cards", "tug_of_war", "before_after_wipe", "versus_split"],
    MotionFamily.PROCESS_FLOW: ["conveyor_belt", "domino_chain", "pipeline_pipes", "funnel_filter", "flow_chain"],
    MotionFamily.RISK_PROB: ["shield_hit", "lock_unlock", "traffic_light", "dice_roll"],
    MotionFamily.CONCEPT_RELATION: ["orbit_system", "layered_onion", "stack_pile", "puzzle_snap", "hub_spoke"],
    MotionFamily.MOCK_UI: ["chat_thread", "terminal_command_run", "form_fill_submit", "mock_card_swipe", "checklist"],
}


def get_recipe_family(recipe_name: str) -> MotionFamily:
    """Return the motion family for a given recipe name (defaulting to NUMBER_STAT)."""
    return RECIPE_FAMILY_MAP.get(recipe_name, MotionFamily.NUMBER_STAT)


def _normalize_text(text: str) -> str:
    norm = unicodedata.normalize("NFD", str(text).casefold()).replace("đ", "d")
    return "".join(c for c in norm if c.isalnum() or c.isspace())


def suggest_metaphor_recipe(narration: str, previous_recipe: Optional[str] = None) -> str:
    """Analyze narration keywords and select the best matching metaphor recipe, avoiding repetition."""
    norm = _normalize_text(narration)
    prev_family = get_recipe_family(previous_recipe) if previous_recipe else None

    # Keyword rules for Metaphors
    scores: Dict[str, int] = {k: 0 for k in RECIPE_FAMILY_MAP.keys()}

    def bump(recipe: str, pts: int = 10):
        scores[recipe] = scores.get(recipe, 0) + pts

    # 1. Compare / VS keywords
    if any(k in norm for k in ["can can", "nang ky", "lech", "can nhac"]):
        bump("balance_scale", 20)
    elif any(k in norm for k in ["so sanh", "doi dau", "uu the"]):
        bump("balance_scale", 10)
    if any(k in norm for k in ["keo co", "giang co", "thi phan", "tranh gianh"]):
        bump("tug_of_war", 20)
    if any(k in norm for k in ["truoc day", "thay doi", "lot xac", "chuyen doi"]):
        bump("before_after_wipe", 20)
    if any(k in norm for k in ["hai phuong an", "mat trai", "uu nhuoc diem", "lat the"]):
        bump("vs_flip_cards", 20)

    # 2. Risk / Probability keywords (Check before broad words)
    if any(k in norm for k in ["khien", "tam khien", "khieng", "phong thu", "an ninh", "chong do", "tan cong"]):
        bump("shield_hit", 30)
    if any(k in norm for k in ["khoa", "mo khoa", "rao can", "then chot"]):
        bump("lock_unlock", 25)
    if any(k in norm for k in ["xac suat", "may rui", "danh cuoc", "canh bac"]):
        bump("dice_roll", 20)
    if any(k in norm for k in ["tin hieu", "den xanh", "den do", "thong suot", "dung lai"]):
        bump("traffic_light", 20)

    # 3. Process / Flow keywords (Use strict phrases to avoid matching "an ninh mang")
    if any(k in norm for k in ["domino", "lan truyen", "he qua lien tiep"]):
        bump("domino_chain", 30)
    elif any(k in norm for k in ["bang chuyen", "day chuyen", "san xuat", "dong dau"]):
        bump("conveyor_belt", 20)
    if any(k in norm for k in ["sang loc", "pheu chuyen doi", "tinh hoa"]):
        bump("funnel_filter", 20)
    if any(k in norm for k in ["duong ong", "van khoa", "dong chay khi", "luu luong"]):
        bump("pipeline_pipes", 20)

    # 4. Concept / Relations keywords
    if any(k in norm for k in ["he sinh thai", "ve tinh quay", "quy dao elip", "mang luoi", "ket noi"]):
        bump("orbit_system", 20)
    if any(k in norm for k in ["boc tach", "tang lop", "ban chat", "goc re"]):
        bump("layered_onion", 20)
    if any(k in norm for k in ["tich luy", "xep chong", "thap the", "ngan xep", "tang bac"]):
        bump("stack_pile", 20)
    if any(k in norm for k in ["manh ghep", "khop noi", "giai phap hoan hao", "khop"]):
        bump("puzzle_snap", 20)

    # 5. Mock UI keywords
    if any(k in norm for k in ["tin nhan", "hoi thoai", "chatbot", "tro chuyen", "tam su"]):
        bump("chat_thread", 20)
    if any(k in norm for k in ["quet the", "phe duyet", "approved", "lua chon"]):
        bump("mock_card_swipe", 20)
    if any(k in norm for k in ["bieu mau", "dang ky", "nhap lieu", "submit"]):
        bump("form_fill_submit", 20)
    if any(k in norm for k in ["lenh", "terminal", "deploy", "trien khai", "code"]):
        bump("terminal_command_run", 20)

    # 6. Number & Fill Level keywords
    if any(k in norm for k in ["do day", "ly nuoc", "song sanh", "muc nuoc"]):
        bump("glass_fill", 15)
    if any(k in norm for k in ["pin", "nang luong", "sac pin", "100%", "buoc dem", "tu chu"]):
        bump("battery_fill", 15)
    if any(k in norm for k in ["nhiet do", "tang nhiet", "soi", "do c"]):
        bump("thermometer", 15)
    if any(k in norm for k in ["dua", "but pha", "vuot troi", "dan dau", "toc do"]):
        bump("bar_race", 15)
    if any(k in norm for k in ["cong to met", "lan banh", "km", "gio van hanh"]):
        bump("odometer", 15)
    if any(k in norm for k in ["ap suat", "dong ho do", "nguong nguy hiem", "ti le", "phan tram"]):
        bump("gauge_needle", 15)
    if any(k in norm for k in ["gach bo", "so cu", "thay vi"]):
        bump("strike_replace", 15)
    if any(k in norm for k in ["ky luc", "ty usd", "trieu", "con so", "chi so"]):
        bump("slot_counter", 10)

    # Sort candidates by score descending
    candidates = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    for recipe, score in candidates:
        if score > 0:
            fam = get_recipe_family(recipe)
            # Avoid consecutive same family
            if prev_family is None or fam != prev_family:
                return recipe

    # Fallback default when no keyword matched: alternate diverse families
    alternating = [
        "slot_counter",
        "balance_scale",
        "conveyor_belt",
        "lock_unlock",
        "orbit_system",
        "glass_fill",
        "chat_thread",
        "bar_race",
        "shield_hit",
        "domino_chain",
        "stack_pile"
    ]
    for alt in alternating:
        if get_recipe_family(alt) != prev_family:
            return alt

    return "slot_counter"


def schedule_recipes_no_repeat(
    scenes: List[Dict[str, Any]],
    min_distinct_recipes: int = 6,
    max_recipe_freq: int = 2,
    min_recipe_distance: int = 4,
    min_distinct_families: int = 4,
    **kwargs: Any,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Enforce strict anti-repetition rules across a sequence of scenes:
    1. Consecutive family rule: No two consecutive scenes share the same motion family.
    2. Distance rule: No identical recipe within 4 consecutive scenes (|i - j| < 4 forbidden).
    3. Frequency rule: Each recipe appears at most 2 times per video.
    4. Diversity rule: At least 6 distinct recipe types per video and >=4 distinct families.
    5. Layout-Recipe pair rule: No two adjacent scenes can share the same (layout, recipe).
    6. Visual beats rule: Each scene must have at least 3 visible events (beats).
    7. Stillness rule: No still interval > 2.5s without an event/idle pulse.
    8. Hook stillness rule: Hook scene cannot stay still > 2.5s.
    9. Evidence grounding: If numbers lack evidence, switch to qualitative recipe.
    Returns (scheduled_scenes, review_notes).
    """
    scheduled: List[Dict[str, Any]] = []
    review_notes: List[str] = []
    target_distinct = min(min_distinct_recipes, len(scenes))
    target_families = min(min_distinct_families, len(scenes))
    used_recipe_counts: Counter[str] = Counter()

    NUMERIC_RECIPES = {
        "slot_counter", "strike_replace", "gauge_needle", "odometer",
        "thermometer", "stat_number", "bar_race", "gauge_ring"
    }

    # Pass 1: Resolve family, distance, frequency, and evidence rules sequentially
    for idx, sc in enumerate(scenes):
        current_recipe = sc.get("recipe") or sc.get("scene_type") or sc.get("template") or "slot_counter"
        narration = sc.get("narration") or sc.get("text") or ""
        evidence = str(sc.get("evidence") or "")
        no_numbers = sc.get("no_numbers", False)
        layout = sc.get("layout") or "center_hero"

        # Check Number Grounding: If recipe requires numbers but no numbers are grounded
        has_number_evidence = bool(re.search(r"\d", evidence) or re.search(r"\d", narration))
        if current_recipe in NUMERIC_RECIPES and (no_numbers or not has_number_evidence):
            old_r = current_recipe
            qualitative_pool = ["balance_scale", "conveyor_belt", "stack_pile", "traffic_light", "puzzle_snap", "lock_unlock", "orbit_system"]
            current_recipe = next((r for r in qualitative_pool if used_recipe_counts[r] < max_recipe_freq), "balance_scale")
            sc["no_numbers"] = True
            review_notes.append(
                f"Cảnh {idx+1}: Recipe số '{old_r}' không có số trong kịch bản; tự động chuyển sang recipe định tính '{current_recipe}'."
            )

        # Enforce Recap scene constraint: final scene must use high-motion recap recipe
        is_recap = (idx == len(scenes) - 1)
        RECAP_RECIPES = ["checklist", "layered_onion", "orbit_system"]
        if is_recap and current_recipe not in RECAP_RECIPES:
            chosen_recap = sorted(RECAP_RECIPES, key=lambda r: used_recipe_counts[r])[0]
            review_notes.append(
                f"Cảnh {idx+1} (Recap cuối): Ép dùng recipe tổng kết rõ nét '{chosen_recap}' (thay vì '{current_recipe}')."
            )
            current_recipe = chosen_recap

        prev_layout = scheduled[-1].get("layout") if scheduled else None
        prev_recipe = scheduled[-1]["scene_type"] if scheduled else None
        prev_family = get_recipe_family(prev_recipe) if prev_recipe else None
        recent_recipes = {scheduled[k]["scene_type"] for k in range(max(0, idx - (min_recipe_distance - 1)), idx)}

        current_family = get_recipe_family(current_recipe)
        violates_fam = (prev_family is not None and current_family == prev_family)
        violates_dist = current_recipe in recent_recipes
        violates_freq = used_recipe_counts[current_recipe] >= max_recipe_freq
        violates_pair = (layout == prev_layout and current_recipe == prev_recipe)

        if violates_fam or violates_dist or violates_freq or violates_pair:
            # Find an alternative recipe from a DIFFERENT family that satisfies all constraints
            candidates_by_family = [
                r for r, fam in RECIPE_FAMILY_MAP.items()
                if (prev_family is None or fam != prev_family)
                and r not in recent_recipes
                and used_recipe_counts[r] < max_recipe_freq
                and not (layout == prev_layout and r == prev_recipe)
            ]

            replacement = candidates_by_family[0] if candidates_by_family else None
            if not replacement:
                for cand in RECIPE_FAMILY_MAP.keys():
                    if cand not in recent_recipes and (prev_family is None or get_recipe_family(cand) != prev_family):
                        replacement = cand
                        break

            replacement = replacement or "orbit_system"
            reason = "trùng family liên tiếp" if violates_fam else "trùng trong 4 cảnh liền kề" if violates_dist else "vượt quá 2 lần/video" if violates_freq else "trùng cặp (layout, recipe)"
            review_notes.append(
                f"Cảnh {idx+1}: Phát hiện recipe '{current_recipe}' {reason}. Tự động đổi sang '{replacement}'."
            )
            current_recipe = replacement

        new_sc = dict(sc)
        new_sc["scene_type"] = current_recipe
        new_sc["recipe"] = current_recipe
        new_sc["motion_family"] = get_recipe_family(current_recipe).value
        new_sc["layout"] = layout
        scheduled.append(new_sc)
        used_recipe_counts[current_recipe] += 1

    # Pass 2: Enforce overall diversity (>= target_distinct distinct recipes and >= target_families distinct families)
    distinct_types = {sc["scene_type"] for sc in scheduled}
    distinct_fams = {sc["motion_family"] for sc in scheduled}
    if len(distinct_types) < target_distinct or len(distinct_fams) < target_families:
        all_candidates = [
            "slot_counter", "balance_scale", "conveyor_belt", "lock_unlock",
            "orbit_system", "battery_fill", "chat_thread", "bar_race",
            "shield_hit", "domino_chain", "stack_pile", "traffic_light",
            "before_after_wipe", "funnel_filter", "layered_onion"
        ]
        unused_pool = [c for c in all_candidates if c not in distinct_types]

        for idx in range(len(scheduled) - 1, -1, -1):
            if len(distinct_types) >= target_distinct and len(distinct_fams) >= target_families:
                break
            old_r = scheduled[idx]["scene_type"]
            old_fam = scheduled[idx]["motion_family"]
            if used_recipe_counts[old_r] <= 1 and len(distinct_fams) >= target_families:
                continue

            prev_fam = scheduled[idx - 1]["motion_family"] if idx > 0 else None
            next_fam = scheduled[idx + 1]["motion_family"] if idx + 1 < len(scheduled) else None

            recent_for_idx = {
                scheduled[k]["scene_type"]
                for k in range(max(0, idx - (min_recipe_distance - 1)), min(len(scheduled), idx + min_recipe_distance))
                if k != idx
            }

            for cand in list(unused_pool):
                cand_fam = get_recipe_family(cand).value
                if cand not in recent_for_idx and cand_fam != prev_fam and cand_fam != next_fam:
                    review_notes.append(
                        f"Tối ưu hóa đa dạng toàn video: Đổi cảnh {idx+1} từ '{old_r}' sang '{cand}' để đạt chỉ tiêu đa dạng hình thức."
                    )
                    scheduled[idx]["scene_type"] = cand
                    scheduled[idx]["recipe"] = cand
                    scheduled[idx]["motion_family"] = cand_fam
                    used_recipe_counts[old_r] -= 1
                    used_recipe_counts[cand] += 1
                    distinct_types.add(cand)
                    distinct_fams = {sc["motion_family"] for sc in scheduled}
                    unused_pool.remove(cand)
                    break

    # Pass 3: Enforce Visual Beats and Stillness constraints (>=3 beats, no gap > 2.5s)
    for idx, sc in enumerate(scheduled):
        dur = float(sc.get("duration") or sc.get("duration_sec") or 4.0)
        beats = sc.get("beats") or []
        if isinstance(beats, list):
            # Normalize beats
            clean_beats = []
            for b in beats:
                if isinstance(b, dict) and "at_sec" in b:
                    clean_beats.append(dict(b))
                elif hasattr(b, "at_sec") and hasattr(b, "action"):
                    clean_beats.append({"at_sec": getattr(b, "at_sec", 0.5), "action": getattr(b, "action", "beat")})
            beats = clean_beats

        # 1. Enforce >= 3 visible events (idle_breath does NOT count as an event)
        meaningful_beats = [b for b in beats if "idle_breath" not in str(b.get("action", "")).lower()]
        if len(meaningful_beats) < 3:
            r_name = sc["scene_type"]
            default_times = [
                round(min(0.5, dur * 0.15), 2),
                round(min(1.8, dur * 0.45), 2),
                round(min(3.2, dur * 0.80), 2)
            ]
            actions = [f"enter_{r_name}", f"action_{r_name}_step", f"impact_{r_name}_glow"]
            for t_val, act in zip(default_times, actions):
                # Only consider meaningful beats when checking for conflicts
                if not any(abs(b["at_sec"] - t_val) < 0.3 and "idle_breath" not in str(b.get("action", "")).lower() for b in beats):
                    beats.append({"at_sec": t_val, "action": act})
            beats.sort(key=lambda b: b["at_sec"])
            review_notes.append(f"Cảnh {idx+1}: Bổ sung nhịp sự kiện trực quan để đạt >= 3 sự kiện.")

        # 2. Enforce stillness constraint (no gap > 2.5s without event / idle movement)
        beats.sort(key=lambda b: b["at_sec"])
        repaired_beats = []
        last_t = 0.0

        for b in beats:
            t_curr = b["at_sec"]
            while t_curr - last_t > 2.5:
                inject_t = round(last_t + 2.0, 2)
                if inject_t < dur:
                    r_name = sc.get("scene_type", "element")
                    repaired_beats.append({"at_sec": inject_t, "action": f"action_{r_name}_step_{len(repaired_beats)+1}"})
                    review_notes.append(f"Cảnh {idx+1}: Phát hiện khoảng tĩnh {t_curr - last_t:.1f}s (>2.5s); bổ sung nhịp diễn hoạt chuyển nấc tại {inject_t}s.")
                last_t = inject_t
            repaired_beats.append(b)
            last_t = t_curr

        # Check trailing interval to scene duration
        while dur - last_t > 2.5:
            inject_t = round(last_t + 2.0, 2)
            if inject_t < dur:
                r_name = sc.get("scene_type", "element")
                repaired_beats.append({"at_sec": inject_t, "action": f"impact_{r_name}_shift_{len(repaired_beats)+1}"})
                review_notes.append(f"Cảnh {idx+1}: Bổ sung giai đoạn trực quan chuyển động tại {inject_t}s để tránh đứng yên.")
            last_t = inject_t

        # 3. Hook stillness constraint: Hook scene cannot stay still > 2.5s
        if idx == 0:
            has_early_action = any(b["at_sec"] <= 2.2 and "idle" not in b["action"] for b in repaired_beats)
            if not has_early_action:
                repaired_beats.insert(1, {"at_sec": 1.2, "action": "hook_hero_punch"})
                review_notes.append("Cảnh 1 (hook): Thêm nhịp hook_hero_punch tại 1.2s để đảm bảo không đứng yên quá 2.5s.")

        repaired_beats.sort(key=lambda b: b["at_sec"])
        sc["beats"] = repaired_beats

        # Enforce headline bounds: <= 6 words, clean
        hl = sc.get("top_headline") or sc.get("headline")
        if hl and isinstance(hl, str):
            hl_words = hl.strip().split()
            if len(hl_words) > 6:
                sc["top_headline"] = " ".join(hl_words[:6])
            else:
                sc["top_headline"] = " ".join(hl_words)

    return scheduled, review_notes



AVAILABLE_SHOT_RECIPES = [
    "slot_counter", "strike_replace", "gauge_needle", "odometer", "bar_race",
    "thermometer", "battery_fill", "glass_fill", "balance_scale", "tug_of_war",
    "vs_flip_cards", "before_after_wipe", "conveyor_belt", "domino_chain",
    "funnel_filter", "pipeline_pipes", "dice_roll", "lock_unlock", "shield_hit",
    "traffic_light", "orbit_system", "layered_onion", "stack_pile", "puzzle_snap",
    "chat_thread", "mock_card_swipe", "form_fill_submit", "terminal_command_run",
    "checklist",
    # 12 New Recipes
    "before_after_split", "timeline_milestones", "map_location_pin",
    "profile_dossier", "document_page_flip", "camera_surveillance_scan",
    "evidence_board", "network_graph", "countdown_timer",
    "courtroom_balance", "code_terminal_window", "quote_dialog_card"
]

NUMERIC_RECIPES = {
    "slot_counter", "strike_replace", "gauge_needle", "odometer",
    "thermometer", "battery_fill", "glass_fill", "bar_race", "countdown_timer"
}


def extract_shot_brief_and_data(text: str, scene_narration: str = "", is_recap: bool = False, spoken_text: str = "") -> dict:
    """Extract semantic intent and factual data for an individual shot without manufactured text."""
    from editor.format_number import parse_display_number
    from agents.presentation import card_phrase

    combined_text = (text.strip() + " " + (spoken_text or scene_narration).strip()).strip()
    norm = _normalize_text(combined_text)

    # 1. Parse number strictly from the shot's spoken audio or shot text (NEVER scene fallback)
    num_source = spoken_text.strip() if spoken_text.strip() else text.strip()
    p_num = parse_display_number(num_source) or (parse_display_number(text.strip()) if text.strip() != num_source else None)
    has_number = p_num is not None
    val = p_num.value if p_num else None
    unit = p_num.unit_display if p_num else ""
    num_text = p_num.formatted_number if p_num else ""

    # Exclude pure calendar date/month/year numbers (e.g. "tháng 10", "năm 2026") from trigger number recipes
    if p_num and val is not None:
        val_int = int(val) if val == int(val) else None
        if val_int is not None:
            val_str = str(val_int)
            date_match = re.search(rf"\b(?:tháng|năm|ngày|quý|thế kỷ)\s+{re.escape(val_str)}\b", combined_text, re.I)
            if date_match:
                stripped_text = re.sub(r"\b(?:tháng|năm|ngày|quý|thế kỷ)\s+\d+\b", "", combined_text, flags=re.I)
                p_rem = parse_display_number(stripped_text)
                if not p_rem or p_rem.value is None:
                    has_number = False
                    val = None
                    unit = ""
                    num_text = ""

    # 2. Extract semantic label strictly from shot text or spoken narration
    clean_lbl = ""
    text_clean = text.strip()
    text_words = text_clean.split()
    norm_text = _normalize_text(text_clean)
    if 2 <= len(text_words) <= 6 and not any(bad in norm_text for bad in ["y chinh", "minh hoa", "chi tiet", "noi dung", "y tuong", "person explaining"]):
        clean_lbl = text_clean
    else:
        clean_lbl = card_phrase(text, scene_narration) if text else ""
        norm_lbl = _normalize_text(clean_lbl)
        lbl_words = [w for w in norm_lbl.split() if len(w) >= 2]
        if (
            not clean_lbl
            or not any(w in norm_text for w in lbl_words)
            or any(bad in norm_lbl for bad in ["y chinh", "minh hoa", "chi tiet", "noi dung", "y tuong", "person explaining"])
        ):
            source_pool = spoken_text or text or scene_narration
            clauses = split_clauses_for_shot(source_pool)
            clean_lbl = clauses[0] if clauses else source_pool
    words_lbl = clean_lbl.split()
    if len(words_lbl) > 6:
        words_lbl = words_lbl[:6]
    INCOMPLETE_TAIL = {
        'thiết', 'ngân', 'của', 'và', 'với', 'trong', 'từ', 'là', 'để', 'cho',
        'nỗ', 'kẻ', 'các', 'những', 'một', 'đang', 'đã', 'sẽ', 'do', 'bởi',
        'vì', 'có', 'lại', 'cũng', 'rất', 'hơn', 'nhất', 'toàn', 'nghiêm',
        'đăng', 'điểm', 'lỗi'
    }
    COMPOUND_TAIL_VALID = {
        'thiết kế', 'thiết bị', 'ngân sách', 'ngân hàng', 'toàn cầu', 'nghiêm trọng',
        'đăng nhập', 'điểm yếu', 'khóa cửa', 'khai thác', 'tấn công', 'đột nhập',
        'xác thực', 'bảo mật', 'an ninh', 'rủi ro', 'phòng thủ', 'doanh nghiệp'
    }
    while len(words_lbl) >= 2:
        last = words_lbl[-1].lower()
        pair = f"{words_lbl[-2].lower()} {last}"
        if pair in COMPOUND_TAIL_VALID:
            break
        if last in INCOMPLETE_TAIL:
            words_lbl.pop()
        else:
            break
    # If the remaining words don't form a meaningful concept (>=2 words), drop the label completely
    clean_lbl = " ".join(words_lbl) if len(words_lbl) >= 2 else ""

    # 3. Determine semantic intent & domain match
    intent = "concept"
    if has_number:
        intent = "number"
    elif is_recap:
        intent = "recap"
    elif any(k in norm for k in ["toa an", "phien toa", "xet xu", "cao trang", "toi danh", "cao buoc", "tham phan", "luat su", "can can"]):
        intent = "legal"
    elif any(k in norm for k in ["ho so", "nhan than", "nghi pham", "doi tuong", "danh tinh", "ly lich"]):
        intent = "profile"
    elif any(k in norm for k in ["dia diem", "thanh pho", "tai", "khu vuc", "bang", "quoc gia", "tinh thanh", "noi dien ra"]):
        intent = "location"
    elif any(k in norm for k in ["chuyen doi", "so voi", "doi lap", "trai nguoc", "hai ben", "truoc va sau", "thay doi"]):
        intent = "compare"
    elif any(k in norm for k in ["an ninh", "canh bao", "giam sat", "camera", "nguy co", "rui ro", "khoa", "ngan chan"]):
        intent = "risk"
    elif any(k in norm for k in ["tien trinh", "moc thoi gian", "giai doan", "nam thang", "chuoi su kien"]):
        intent = "process"
    elif any(k in norm for k in ["mang luoi", "lien ket", "so do", "he thong"]):
        intent = "network"
    elif any(k in norm for k in ["lenh", "ma doc", "terminal", "he thong", "du lieu", "tai lieu"]):
        intent = "mock_ui"

    return {
        "text": text,
        "label": clean_lbl,
        "intent": intent,
        "has_number": has_number,
        "value": val,
        "unit": unit,
        "number_text": num_text,
        "is_recap": is_recap,
    }


def split_clauses_for_shot(text: str) -> list[str]:
    """Split sentence into natural clauses/items based on punctuation and conjunctions."""
    raw_parts = re.split(r"[,\.;:\?!]|(?:và|cùng|nhưng|tuy nhiên|thay vì|đồng thời|với|đối mặt với)", text, flags=re.I)
    cleaned = []
    for p in raw_parts:
        c = re.sub(r"\s+", " ", p).strip()
        if len(c.split()) >= 2:
            cleaned.append(c)
    if not cleaned:
        words = text.strip().split()
        if len(words) > 6:
            mid = len(words) // 2
            cleaned = [" ".join(words[:mid]), " ".join(words[mid:])]
        else:
            cleaned = [text.strip()]
    return cleaned


def build_shot_factual_data(recipe: str, brief_info: dict, text: str, scene_narration: str) -> dict:
    """Build factual data schema strictly from the shot's spoken sentence.
    All labels, items, left/right labels, and status MUST be extracted directly from
    the shot's text/narration. No placeholder or manufactured strings allowed.
    """
    data: dict = {
        "label": brief_info["label"],
        "text": brief_info["label"],
    }
    if brief_info["has_number"]:
        data["value"] = brief_info["value"]
        data["unit"] = brief_info["unit"]
        data["number_text"] = brief_info["number_text"]

    clauses = split_clauses_for_shot(text)
    if not clauses and scene_narration:
        clauses = split_clauses_for_shot(scene_narration)

    # Extract proper nouns / capitalized multi-word phrases directly from sentence
    proper_nouns = re.findall(r"\b[A-ZÀ-Ỹ][a-zà-ỹ0-9_]*(?:\s+[A-ZÀ-Ỹ][a-zà-ỹ0-9_]*)+\b", text)
    if not proper_nouns and scene_narration:
        proper_nouns = re.findall(r"\b[A-ZÀ-Ỹ][a-zà-ỹ0-9_]*(?:\s+[A-ZÀ-Ỹ][a-zà-ỹ0-9_]*)+\b", scene_narration)
    main_name = proper_nouns[0] if proper_nouns else (clauses[0] if clauses else brief_info["label"])
    main_name = " ".join(main_name.split()[:4])

    if recipe in {"courtroom_balance", "balance_scale", "versus_split", "before_after_split", "before_after_wipe"}:
        if len(clauses) >= 2:
            data["left_label"] = " ".join(clauses[0].split()[:3])
            data["right_label"] = " ".join(clauses[1].split()[:3])
        else:
            words = text.split()
            if len(words) >= 4:
                data["left_label"] = " ".join(words[:2])
                data["right_label"] = " ".join(words[-2:])
            else:
                data["left_label"] = brief_info["label"]
                data["right_label"] = ""
        data["title"] = " ".join(brief_info["label"].split()[:3])

    elif recipe == "profile_dossier":
        data["name"] = main_name
        if len(clauses) >= 2:
            data["role"] = " ".join(clauses[1].split()[:3])
        if len(clauses) >= 3:
            data["status"] = " ".join(clauses[2].split()[:3])
        data["details"] = [" ".join(c.split()[:4]) for c in clauses[:3]]

    elif recipe == "map_location_pin":
        match_loc = re.search(r"\b(?:tại|ở|khu vực|thành phố|tỉnh|bang|nước)\s+([A-ZÀ-Ỹa-zà-ỹ0-9_\s]{2,20})", text, re.I)
        loc = proper_nouns[0] if proper_nouns else (match_loc.group(1).strip() if match_loc else " ".join(text.split()[:3]))
        data["location"] = " ".join(loc.split()[:4])

    elif recipe == "timeline_milestones":
        data["milestones"] = [{"label": " ".join(c.split()[:3])} for c in clauses[:4]]

    elif recipe == "document_page_flip":
        data["title"] = " ".join(brief_info["label"].split()[:4])
        data["lines"] = [" ".join(c.split()[:4]) for c in clauses[:3]]

    elif recipe == "camera_surveillance_scan":
        data["target"] = main_name
        if len(clauses) >= 2:
            data["status"] = " ".join(clauses[1].split()[:3])

    elif recipe == "evidence_board":
        data["items"] = [" ".join(c.split()[:4]) for c in clauses[:3]]

    elif recipe == "network_graph":
        data["center_node"] = " ".join(main_name.split()[:2])
        data["nodes"] = [" ".join(c.split()[:2]) for c in clauses[1:4]]

    elif recipe == "countdown_timer":
        data["value"] = brief_info.get("value") or 10
        data["label"] = " ".join(brief_info["label"].split()[:3])

    elif recipe == "code_terminal_window":
        clean_kw = re.sub(r"[^a-zA-Z0-9_]", "", _normalize_text(brief_info["label"]))[:12]
        data["command"] = f"run --{clean_kw or 'check'}"
        data["lines"] = [" ".join(c.split()[:4]) for c in clauses[:3]]

    elif recipe == "quote_dialog_card":
        data["quote"] = text.strip()
        data["author"] = main_name

    elif recipe == "checklist":
        data["items"] = [" ".join(c.split()[:4]) for c in clauses[:4]]

    elif recipe == "lock_unlock":
        if len(clauses) >= 2:
            data["status"] = " ".join(clauses[1].split()[:3]).upper()

    elif recipe == "orbit_system":
        data["center_node"] = " ".join(clauses[0].split()[:3]) if clauses else brief_info["label"]
        if len(clauses) >= 2:
            data["satellites"] = [" ".join(c.split()[:3]) for c in clauses[1:4]]
        else:
            data["satellites"] = [" ".join(w.split()[:2]) for w in clauses[:2]]
        data["label"] = brief_info["label"]

    elif recipe == "layered_onion":
        data["core_text"] = " ".join(clauses[0].split()[:3]) if clauses else brief_info["label"]
        if len(clauses) >= 2:
            data["layers"] = [" ".join(c.split()[:3]) for c in clauses[1:4]]
        else:
            data["layers"] = [" ".join(w.split()[:2]) for w in clauses[:2]]
        data["label"] = brief_info["label"]

    elif recipe == "stack_pile":
        data["layers"] = [" ".join(c.split()[:3]) for c in clauses[:4]]
        data["label"] = brief_info["label"]

    elif recipe == "puzzle_snap":
        data["solution_text"] = " ".join(clauses[0].split()[:3]) if clauses else brief_info["label"]
        data["label"] = brief_info["label"]

    elif recipe == "steps_ladder":
        data["steps"] = [" ".join(c.split()[:3]) for c in clauses[:4]]
        data["label"] = brief_info["label"]

    elif recipe == "stack_cards":
        data["items"] = [" ".join(c.split()[:4]) for c in clauses[:3]]
        data["label"] = brief_info["label"]

    elif recipe == "hub_spoke":
        data["center_node"] = " ".join(clauses[0].split()[:3]) if clauses else brief_info["label"]
        if len(clauses) >= 2:
            data["spokes"] = [" ".join(c.split()[:3]) for c in clauses[1:5]]
        data["label"] = brief_info["label"]

    return data


def validate_recipe_fit(recipe: str, shot_data: dict, text: str, scene_narration: str) -> bool:
    """Validate that labels on the recipe contain keywords present in narration or brief."""
    norm_script = _normalize_text(text + " " + scene_narration)

    # Check every string in shot_data: it must contain words grounded in text/narration or be numeric/structural
    for k, v in shot_data.items():
        if k in {"value", "unit", "number_text", "action", "at_sec", "beats", "theme", "layout", "command"}:
            continue
        if isinstance(v, str):
            norm_val = _normalize_text(v)
            if norm_val in {"minh hoa y tuong", "y chinh can nho", "chi tiet", "noi dung", "none", ""}:
                return False
            # Check if at least one meaningful word in norm_val appears in norm_script
            val_words = [w for w in norm_val.split() if len(w) >= 2]
            if val_words and not any(w in norm_script for w in val_words):
                return False
        elif isinstance(v, list):
            for item in v:
                if isinstance(item, str):
                    norm_item = _normalize_text(item)
                    if norm_item in {"minh hoa y tuong", "y chinh can nho", "chi tiet", "noi dung", "none", ""}:
                        return False
                    item_words = [w for w in norm_item.split() if len(w) >= 2]
                    if item_words and not any(w in norm_script for w in item_words):
                        return False
                elif isinstance(item, dict):
                    lbl_sub = item.get("label") or item.get("text")
                    if lbl_sub and isinstance(lbl_sub, str):
                        norm_sub = _normalize_text(lbl_sub)
                        sub_words = [w for w in norm_sub.split() if len(w) >= 2]
                        if sub_words and not any(w in norm_script for w in sub_words):
                            return False

    # Recipes cannot have empty content
    lbl = shot_data.get("label") or shot_data.get("text") or shot_data.get("title") or shot_data.get("name")
    if not lbl or not str(lbl).strip():
        return False
    return True


def enough_for_shot(recipe: str, brief_info: dict, text: str = "", shot_data: dict | None = None) -> bool:
    """Verify strictly if the shot has sufficient factual data for the recipe."""
    if recipe in NUMERIC_RECIPES:
        return bool(brief_info.get("has_number") and brief_info.get("value") is not None)

    if shot_data is None:
        shot_data = {}

    clauses = split_clauses_for_shot(text or brief_info.get("text", ""))

    if recipe in {"courtroom_balance", "balance_scale", "versus_split", "before_after_split", "before_after_wipe"}:
        left = shot_data.get("left_label")
        right = shot_data.get("right_label")
        if not left or not right or left == right:
            if len(clauses) < 2 and len((text or "").split()) < 4:
                return False

    if recipe in {"checklist", "evidence_board"}:
        items = shot_data.get("items") or []
        if len(items) < 2 and len(clauses) < 2:
            return False

    if recipe in {"timeline_milestones"}:
        mstones = shot_data.get("milestones") or []
        if len(mstones) < 2 and len(clauses) < 2:
            return False

    if recipe in {"network_graph"}:
        nodes = shot_data.get("nodes") or []
        if len(nodes) < 2 and len(clauses) < 3:
            return False

    # Empty / generic card prohibition
    lbl = (shot_data.get("label") or brief_info.get("label", "") or brief_info.get("text", "")).strip()
    norm_lbl = _normalize_text(lbl)
    if not lbl or norm_lbl in {"chi tiet", "minh hoa", "y chinh", "none", "", "y chinh can nho", "minh hoa y tuong"}:
        return False

    return True


TRANSITION_TYPES = [
    "morph_anchor",
    "directional_wipe",
    "zoom_through",
    "particle_dissolve",
    "mask_reveal",
]


def schedule_shots_no_repeat(
    shots_data: list[dict],
    min_distinct: int = 10,
    min_dist: int = 4,
    max_freq: int = 2
) -> tuple[list[dict], list[str]]:
    """
    Schedule recipes across all shots of the video adhering to:
    - min_dist = 4 (no repeat of same recipe in 4 consecutive shots)
    - max_freq = 2 (each recipe used at most 2 times across video)
    - min_distinct = 10 (at least 10 distinct recipes for a 60s video)
    - recipe_fit metadata explaining the match
    - 5 transition styles between shots without consecutive repetition
    - Persistent anchor across shots
    - Factual data extracted strictly from spoken words
    """
    scheduled = []
    review_notes = []
    used_counts = Counter()
    total_shots = len(shots_data)

    target_distinct = min(min_distinct, total_shots)

    INTENT_RECIPE_PRIORITY = {
        "legal": [
            "courtroom_balance", "profile_dossier", "document_page_flip",
            "camera_surveillance_scan", "evidence_board", "balance_scale"
        ],
        "profile": ["profile_dossier", "document_page_flip", "camera_surveillance_scan", "quote_dialog_card"],
        "location": ["map_location_pin", "network_graph", "camera_surveillance_scan"],
        "number": [
            "slot_counter", "odometer", "strike_replace", "countdown_timer",
            "gauge_needle", "battery_fill", "glass_fill", "bar_race", "thermometer"
        ],
        "compare": ["before_after_split", "balance_scale", "courtroom_balance", "vs_flip_cards", "tug_of_war", "before_after_wipe"],
        "risk": ["shield_hit", "lock_unlock", "camera_surveillance_scan", "traffic_light", "dice_roll"],
        "process": ["timeline_milestones", "pipeline_pipes", "domino_chain", "conveyor_belt", "funnel_filter"],
        "network": ["network_graph", "evidence_board", "orbit_system", "puzzle_snap"],
        "mock_ui": ["code_terminal_window", "form_fill_submit", "mock_card_swipe", "chat_thread", "terminal_command_run", "checklist"],
        "concept": ["evidence_board", "orbit_system", "puzzle_snap", "stack_pile", "layered_onion"],
        "recap": ["checklist", "timeline_milestones", "evidence_board", "orbit_system", "lock_unlock"],
    }

    # Central anchor metaphor determined dynamically from script content via score
    all_text = " ".join((sh.get("narration") or sh.get("text") or "") for sh in shots_data)
    norm_all = _normalize_text(all_text)
    domain_scores = {
        "finance": sum(1 for k in ["co phieu", "chung khoan", "gia vang", "thi truong", "doanh thu", "loi nhuan", "tai chinh", "dau tu", "ngan hang"] if k in norm_all),
        "tech": sum(1 for k in ["cong nghe", "phan mem", "he thong", "du lieu", "ky thuat", "huong dan", "thiet bi", "chip", "ai", "code", "docker", "python"] if k in norm_all),
        "legal": sum(1 for k in ["phap ly", "toa an", "xet xu", "vu an", "luat", "dieu tra", "cao trang", "hoi dong", "kiem sat", "bao chua", "nghi an", "ban an"] if k in norm_all),
    }
    best_domain = max(domain_scores, key=domain_scores.get)
    if domain_scores[best_domain] == 0:
        central_anchor_name = "Mô hình & Chuỗi Diễn tiến"
        anchor_elem = "timeline_milestones"
    elif best_domain == "finance":
        central_anchor_name = "Chỉ số & Cột mốc Thị trường"
        anchor_elem = "bar_race"
    elif best_domain == "legal":
        central_anchor_name = "Hồ sơ & Cán cân Pháp lý"
        anchor_elem = "courtroom_balance"
    elif best_domain == "tech":
        central_anchor_name = "Hệ thống & Cấu trúc Kỹ thuật"
        anchor_elem = "network_graph"

    for idx, sh in enumerate(shots_data):
        card_t = sh.get("card_text") or sh.get("text") or ""
        spk_t = sh.get("narration") or ""
        text = card_t or spk_t
        scene_narration = sh.get("scene_narration") or text
        is_recap = bool(sh.get("is_recap") or idx == total_shots - 1)

        brief_info = extract_shot_brief_and_data(text, scene_narration, is_recap=is_recap, spoken_text=spk_t)
        intent = brief_info["intent"]

        # Build candidate pool prioritizing intent
        candidate_pool = list(INTENT_RECIPE_PRIORITY.get(intent, []))
        for r in AVAILABLE_SHOT_RECIPES:
            if r not in candidate_pool:
                candidate_pool.append(r)

        # Distance window: check previous min_dist shots
        recent_recipes = [s["recipe"] for s in scheduled[max(0, idx - min_dist):idx]]

        chosen_recipe = None
        # Strict pass 1: Respect candidate priority, min_dist (4) and max_freq (2)
        for cand in candidate_pool:
            if cand in recent_recipes or used_counts[cand] >= max_freq:
                continue
            if not enough_for_shot(cand, brief_info):
                continue
            tentative_data = build_shot_factual_data(cand, brief_info, text, scene_narration)
            if not validate_recipe_fit(cand, tentative_data, text, scene_narration):
                continue
            chosen_recipe = cand
            break

        # Pass 2: Search entire catalog for recipes satisfying min_dist (4) and max_freq (2)
        if not chosen_recipe:
            for cand in AVAILABLE_SHOT_RECIPES:
                if cand in recent_recipes or used_counts[cand] >= max_freq:
                    continue
                if not enough_for_shot(cand, brief_info):
                    continue
                tentative_data = build_shot_factual_data(cand, brief_info, text, scene_narration)
                if validate_recipe_fit(cand, tentative_data, text, scene_narration):
                    chosen_recipe = cand
                    break

        # Pass 3: If candidate_pool exhausted, step-down distance to 3 then 2, but NEVER exceed max_freq (2)!
        if not chosen_recipe:
            for d_step in [3, 2, 1]:
                sub_rec = recent_recipes[max(0, len(recent_recipes) - d_step):]
                for cand in AVAILABLE_SHOT_RECIPES:
                    if cand in sub_rec or used_counts[cand] >= max_freq:
                        continue
                    if not enough_for_shot(cand, brief_info):
                        continue
                    tentative_data = build_shot_factual_data(cand, brief_info, text, scene_narration)
                    if validate_recipe_fit(cand, tentative_data, text, scene_narration):
                        chosen_recipe = cand
                        break
                if chosen_recipe:
                    break

        # Ultimate fallback: Pick recipe with absolute minimum usage, not immediate previous
        if not chosen_recipe:
            cand_least = min(
                (r for r in AVAILABLE_SHOT_RECIPES if not recent_recipes or r != recent_recipes[-1]),
                key=lambda r: used_counts[r],
                default="pipeline_pipes"
            )
            chosen_recipe = cand_least

        used_counts[chosen_recipe] += 1

        dur = float(sh.get("duration") or sh.get("duration_sec") or 3.0)

        # Generate animated beats (>= 3 visible beats per shot)
        shot_beats = [
            {"at_sec": round(min(0.3, dur * 0.15), 2), "action": f"enter_{chosen_recipe}"},
            {"at_sec": round(min(1.5, dur * 0.50), 2), "action": f"action_{chosen_recipe}_step"},
            {"at_sec": round(min(dur - 0.3, dur * 0.85), 2), "action": f"impact_{chosen_recipe}_glow"}
        ]

        # Extract factual data strictly grounded in narration
        shot_data = build_shot_factual_data(chosen_recipe, brief_info, text, scene_narration)

        # Select transition between shots (5 styles, no consecutive repetition)
        prev_transition = scheduled[-1].get("transition") if scheduled else None
        trans_candidates = [t for t in TRANSITION_TYPES if t != prev_transition]
        if intent in {"legal", "compare"}:
            chosen_trans = "morph_anchor" if "morph_anchor" in trans_candidates else trans_candidates[0]
        elif intent in {"risk", "process"}:
            chosen_trans = "directional_wipe" if "directional_wipe" in trans_candidates else trans_candidates[0]
        elif intent in {"location", "network"}:
            chosen_trans = "zoom_through" if "zoom_through" in trans_candidates else trans_candidates[0]
        elif intent in {"mock_ui", "profile"}:
            chosen_trans = "mask_reveal" if "mask_reveal" in trans_candidates else trans_candidates[0]
        else:
            chosen_trans = trans_candidates[0]

        # Persistent anchor state for this shot
        anchor_state = f"giai_doan_{idx+1}"

        new_sh = dict(sh)
        new_sh["recipe"] = chosen_recipe
        new_sh["scene_type"] = chosen_recipe
        new_sh["beats"] = shot_beats
        new_sh["data"] = shot_data
        new_sh["brief_info"] = brief_info
        new_sh["transition"] = chosen_trans
        new_sh["anchor"] = {
            "metaphor_name": central_anchor_name,
            "anchor_element": anchor_elem,
            "state": anchor_state,
        }
        new_sh["recipe_fit"] = {
            "recipe": chosen_recipe,
            "intent": intent,
            "reason": f"Khớp ý nghĩa câu: '{text[:35]}...' (ý chính: {brief_info['label']})",
        }
        scheduled.append(new_sh)

    # Pass 2: Ensure >= target_distinct recipes across video
    distinct_types = {s["recipe"] for s in scheduled}
    if len(distinct_types) < target_distinct:
        pool = [r for r in AVAILABLE_SHOT_RECIPES if r not in distinct_types]
        for idx in range(len(scheduled) - 1, -1, -1):
            if len(distinct_types) >= target_distinct or not pool:
                break
            if scheduled[idx].get("is_recap") or idx == len(scheduled) - 1:
                continue
            cur_r = scheduled[idx]["recipe"]
            if used_counts[cur_r] <= 1:
                continue
            recent_idx = {scheduled[k]["recipe"] for k in range(max(0, idx - 2), min(len(scheduled), idx + 3)) if k != idx}
            b_info = scheduled[idx].get("brief_info", {})
            sh_txt = scheduled[idx].get("narration") or scheduled[idx].get("text") or ""
            sc_narration = scheduled[idx].get("scene_narration") or sh_txt
            for candidate in list(pool):
                if candidate not in recent_idx and enough_for_shot(candidate, b_info):
                    c_data = build_shot_factual_data(candidate, b_info, sh_txt, sc_narration)
                    if validate_recipe_fit(candidate, c_data, sh_txt, sc_narration):
                        scheduled[idx]["recipe"] = candidate
                        scheduled[idx]["scene_type"] = candidate
                        scheduled[idx]["data"] = c_data
                        scheduled[idx]["recipe_fit"] = {
                            "recipe": candidate,
                            "intent": b_info.get("intent", "general"),
                            "reason": f"Tối ưu đa dạng toàn video: khớp câu '{sh_txt[:35]}...'",
                        }
                        used_counts[cur_r] -= 1
                        used_counts[candidate] += 1
                        distinct_types.add(candidate)
                        pool.remove(candidate)
                        review_notes.append(f"Shot {idx+1}: Tối ưu đa dạng toàn video (>=10 loại), đổi sang recipe '{candidate}'.")
                        break

    return scheduled, review_notes