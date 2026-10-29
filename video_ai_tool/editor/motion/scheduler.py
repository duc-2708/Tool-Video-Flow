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

        # 1. Enforce >= 3 visible events
        if len(beats) < 3:
            r_name = sc["scene_type"]
            default_times = [
                round(min(0.5, dur * 0.15), 2),
                round(min(1.8, dur * 0.45), 2),
                round(min(3.2, dur * 0.80), 2)
            ]
            actions = [f"enter_{r_name}", f"action_{r_name}_step", f"impact_{r_name}_glow"]
            for t_val, act in zip(default_times, actions):
                if not any(abs(b["at_sec"] - t_val) < 0.4 for b in beats):
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
                    repaired_beats.append({"at_sec": inject_t, "action": "idle_pulse"})
                    review_notes.append(f"Cảnh {idx+1}: Phát hiện khoảng tĩnh {t_curr - last_t:.1f}s (>2.5s); chèn nhịp idle_pulse tại {inject_t}s.")
                last_t = inject_t
            repaired_beats.append(b)
            last_t = t_curr

        # Check trailing interval to scene duration
        while dur - last_t > 2.5:
            inject_t = round(last_t + 2.0, 2)
            if inject_t < dur:
                repaired_beats.append({"at_sec": inject_t, "action": "idle_breath"})
                review_notes.append(f"Cảnh {idx+1}: Chèn nhịp idle_breath tại {inject_t}s để tránh đứng yên cuối cảnh.")
            last_t = inject_t

        # 3. Hook stillness constraint: Hook scene cannot stay still > 2.5s
        if idx == 0:
            has_early_action = any(b["at_sec"] <= 2.2 and "idle" not in b["action"] for b in repaired_beats)
            if not has_early_action:
                repaired_beats.insert(1, {"at_sec": 1.2, "action": "hook_hero_punch"})
                review_notes.append("Cảnh 1 (hook): Thêm nhịp hook_hero_punch tại 1.2s để đảm bảo không đứng yên quá 2.5s.")

        repaired_beats.sort(key=lambda b: b["at_sec"])
        sc["beats"] = repaired_beats

    return scheduled, review_notes
