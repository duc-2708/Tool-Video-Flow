"""Anti-Repetition Scheduler & Metaphor-First Planner for Motion Vocabulary Recipes.
Enforces diverse visual metaphors and forbids consecutive scenes from sharing the same motion family.
"""
from __future__ import annotations

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


# Recipe to Family Mapping (28 Recipes)
RECIPE_FAMILY_MAP: Dict[str, MotionFamily] = {
    # Phase A
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
}

# Cross-Family Equivalence Map for Auto-Repair
FAMILY_ALTERNATIVES: Dict[MotionFamily, List[str]] = {
    MotionFamily.NUMBER_STAT: ["slot_counter", "odometer", "strike_replace", "thermometer"],
    MotionFamily.FILL_LEVEL: ["battery_fill", "glass_fill", "container_fill"],
    MotionFamily.COMPARE_VS: ["balance_scale", "vs_flip_cards", "tug_of_war", "before_after_wipe"],
    MotionFamily.PROCESS_FLOW: ["conveyor_belt", "domino_chain", "pipeline_pipes", "funnel_filter"],
    MotionFamily.RISK_PROB: ["shield_hit", "lock_unlock", "traffic_light", "dice_roll"],
    MotionFamily.CONCEPT_RELATION: ["orbit_system", "layered_onion", "stack_pile", "puzzle_snap"],
    MotionFamily.MOCK_UI: ["chat_thread", "terminal_command_run", "form_fill_submit", "mock_card_swipe"],
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
    if any(k in norm for k in ["he sinh thai", "ve tinh quay", "quy dao elip"]):
        bump("orbit_system", 20)
    if any(k in norm for k in ["boc tach", "tang lop", "ban chat", "goc re"]):
        bump("layered_onion", 20)
    if any(k in norm for k in ["tich luy", "xep chong", "thap the", "ngan xep"]):
        bump("stack_pile", 20)
    if any(k in norm for k in ["manh ghep", "khop noi", "giai phap hoan hao"]):
        bump("puzzle_snap", 20)

    # 5. Mock UI keywords
    if any(k in norm for k in ["tin nhan", "hoi thoai", "chatbot", "tro chuyen"]):
        bump("chat_thread", 20)
    if any(k in norm for k in ["quet the", "phe duyet", "approved", "lua chon"]):
        bump("mock_card_swipe", 20)
    if any(k in norm for k in ["bieu mau", "dang ky", "nhap lieu", "submit"]):
        bump("form_fill_submit", 20)
    if any(k in norm for k in ["lenh", "terminal", "deploy", "trien khai"]):
        bump("terminal_command_run", 20)

    # 6. Number & Fill Level keywords
    if any(k in norm for k in ["do day", "ly nuoc", "song sanh", "muc nuoc"]):
        bump("glass_fill", 15)
    if any(k in norm for k in ["pin", "nang luong", "sac pin", "100%"]):
        bump("battery_fill", 15)
    if any(k in norm for k in ["nhiet do", "tang nhiet", "soi", "do c"]):
        bump("thermometer", 15)
    if any(k in norm for k in ["dua", "but pha", "vuot troi", "dan dau"]):
        bump("bar_race", 15)
    if any(k in norm for k in ["cong to met", "lan banh", "km"]):
        bump("odometer", 15)
    if any(k in norm for k in ["ap suat", "dong ho do", "nguong nguy hiem"]):
        bump("gauge_needle", 15)
    if any(k in norm for k in ["gach bo", "so cu"]):
        bump("strike_replace", 15)
    if any(k in norm for k in ["ky luc", "ty usd", "trieu", "con so"]):
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
        "chat_thread"
    ]
    for alt in alternating:
        if get_recipe_family(alt) != prev_family:
            return alt

    return "slot_counter"


def schedule_recipes_no_repeat(
    scenes: List[Dict[str, Any]],
    min_distinct_families: int = 4
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Enforce strict anti-repetition rules across a sequence of scenes:
    1. Forbid two consecutive scenes from sharing the same MotionFamily.
    2. Require at least min_distinct_families across a 5-7 scene video.
    Returns (scheduled_scenes, review_notes).
    """
    scheduled: List[Dict[str, Any]] = []
    review_notes: List[str] = []
    seen_families: set[MotionFamily] = set()

    # Pass 1: Resolve consecutive repetitions
    for idx, sc in enumerate(scenes):
        current_recipe = sc.get("scene_type") or sc.get("template") or "slot_counter"
        narration = sc.get("narration") or sc.get("text") or ""
        current_family = get_recipe_family(current_recipe)

        prev_recipe = scheduled[-1]["scene_type"] if scheduled else None
        prev_family = get_recipe_family(prev_recipe) if prev_recipe else None

        # Check consecutive repetition rule
        if prev_family is not None and current_family == prev_family:
            # Need to swap to an equivalent recipe from a different family
            candidate_recipe = suggest_metaphor_recipe(narration, previous_recipe=prev_recipe)
            candidate_family = get_recipe_family(candidate_recipe)

            # If still same family, pick from a guaranteed different family
            if candidate_family == prev_family:
                for fam, pool in FAMILY_ALTERNATIVES.items():
                    if fam != prev_family and fam not in seen_families:
                        candidate_recipe = pool[0]
                        candidate_family = fam
                        break
                if candidate_family == prev_family:
                    for fam, pool in FAMILY_ALTERNATIVES.items():
                        if fam != prev_family:
                            candidate_recipe = pool[0]
                            candidate_family = fam
                            break

            review_notes.append(
                f"Cảnh {idx+1}: Phát hiện lặp họ '{current_family.value}' liên tiếp với cảnh {idx}. "
                f"Tự động đổi recipe từ '{current_recipe}' sang '{candidate_recipe}' ({candidate_family.value})."
            )
            current_recipe = candidate_recipe
            current_family = candidate_family

        new_sc = dict(sc)
        new_sc["scene_type"] = current_recipe
        new_sc["motion_family"] = current_family.value
        scheduled.append(new_sc)
        seen_families.add(current_family)

    # Pass 2: Enforce overall distinct family count (min_distinct_families)
    current_distinct = {sc["motion_family"] for sc in scheduled}
    if len(scheduled) >= 5 and len(current_distinct) < min_distinct_families:
        unused_families = [f for f in MotionFamily if f.value not in current_distinct]
        fam_counts = Counter(sc["motion_family"] for sc in scheduled)

        for idx in range(len(scheduled) - 1, -1, -1):
            if len(current_distinct) >= min_distinct_families or not unused_families:
                break
            old_fam = scheduled[idx]["motion_family"]
            # Only swap scenes whose family appears more than once, to prevent reducing distinct families
            if fam_counts[old_fam] <= 1:
                continue

            prev_fam = scheduled[idx - 1]["motion_family"] if idx > 0 else None
            next_fam = scheduled[idx + 1]["motion_family"] if idx + 1 < len(scheduled) else None

            # Find an unused family that doesn't conflict with neighbors
            for candidate_fam in list(unused_families):
                if (prev_fam is None or candidate_fam.value != prev_fam) and (next_fam is None or candidate_fam.value != next_fam):
                    swap_recipe = FAMILY_ALTERNATIVES[candidate_fam][0]
                    old_recipe = scheduled[idx]["scene_type"]
                    review_notes.append(
                        f"Tối ưu hóa phân bổ họ chuyển động toàn video: Đổi cảnh {idx+1} từ '{old_recipe}' "
                        f"sang '{swap_recipe}' ({candidate_fam.value}) để đạt chỉ tiêu >= {min_distinct_families} họ."
                    )
                    scheduled[idx]["scene_type"] = swap_recipe
                    scheduled[idx]["motion_family"] = candidate_fam.value
                    fam_counts[old_fam] -= 1
                    fam_counts[candidate_fam.value] += 1
                    current_distinct.add(candidate_fam.value)
                    unused_families.remove(candidate_fam)
                    break

    return scheduled, review_notes
