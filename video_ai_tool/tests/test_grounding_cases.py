"""
Automated regression test suite executing cases from tests/fixtures/grounding_cases.yaml.
"""
from pathlib import Path
import pytest
import yaml

from validation.grounding import (
    normalize_number,
    extract_numbers,
    numbers_match,
    normalize_entity,
    extract_entities,
    entity_matches,
    classify_claim,
    match_to_facts,
)

CASES_FILE = Path(__file__).parent / "fixtures" / "grounding_cases.yaml"


def load_all_cases():
    data = yaml.safe_load(CASES_FILE.read_text(encoding="utf-8"))
    return data["historical_cases"], data["random_cases"]


HISTORICAL_CASES, RANDOM_CASES = load_all_cases()


@pytest.mark.parametrize("case", HISTORICAL_CASES, ids=lambda c: c["id"])
def test_historical_grounding_case(case):
    cid = case["id"]
    category = case["category"]

    if category == "entity":
        # Candidate at sentence start should not be an entity
        entities = extract_entities(case["text"])
        ent_names = [e.raw.lower() for e in entities]
        first_word = case["text"].split()[0].lower()
        assert (first_word in ent_names) == case["expect_entity_detected"]

    elif category == "entity_match":
        cand = case["candidate"]
        target = case["target"]
        assert entity_matches(cand, target) == case["expect_match"]

    elif category == "number_match":
        cand = case["candidate"]
        target = case["target"]
        assert numbers_match(cand, target) == case["expect_match"]

    elif category == "date_token":
        text = case["text"]
        nums = [n.canonical_str() for n in extract_numbers(text, ignore_current_year=False)]
        assert case["forbidden_number"] not in nums
        for expected in case["expected_numbers"]:
            assert expected in nums

    elif category == "source_leak":
        text = case["text"]
        channel = case["channel_name"]
        allowed = case["allowed_sources"]
        # The channel name is in text and not in allowed sources
        assert channel in text
        assert channel not in allowed

    elif category == "cta_classification":
        text = case["text"]
        classification = classify_claim(text, sentence_type="cta")
        assert classification["is_assertion"] == case["expect_assertion"]

    elif category == "visual_grounding_repair":
        vis_num = case["visual_number"]
        fact_num = case["fact_number"]
        assert numbers_match(vis_num, fact_num)
        fact_norm = normalize_number(fact_num)
        assert fact_norm.canonical_str() == case["expect_repair_to"]

    elif category == "vietnamese_accent":
        from utils.vietnamese_accent import is_unaccented_vietnamese
        text = case["text"]
        is_bad, _ = is_unaccented_vietnamese(text)
        assert is_bad == case["expect_unaccented"]


@pytest.mark.parametrize("case", RANDOM_CASES, ids=lambda c: c["id"])
def test_random_grounding_case(case):
    cand = case["candidate"]
    target = case["target"]
    assert numbers_match(cand, target) == case["expect_match"]
