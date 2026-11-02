from datetime import date
import re

from ml02.models import CandidateFeatures, ViewerFeatures
from ml02.ranker import rank_candidates

FIXED_DATE = date(2026, 11, 1)


def test_single_and_multiple_shared_interest_reason_codes_are_deterministic():
    viewer = ViewerFeatures("viewer-1", frozenset({"ai", "python", "dbms"}), "collaboration")
    candidates = [
        CandidateFeatures(
            "one", frozenset({"ai", "music"}), 1.0, 0.8, 0.9,
            interest_labels={"ai": "artificial-intelligence"},
            intent_reason_code="INTENT_MATCH_COLLABORATION",
        ),
        CandidateFeatures(
            "two", frozenset({"ai", "python", "music"}), 1.0, 0.8, 0.9,
            interest_labels={"ai": "artificial-intelligence", "python": "python"},
            intent_reason_code="INTENT_MATCH_COLLABORATION",
        ),
    ]
    result = rank_candidates(viewer, candidates, ranking_date=FIXED_DATE)
    by_id = {x.candidate_id: x for x in result.recommendations}
    assert by_id["one"].feature_scores.interest == 0.25
    assert by_id["two"].feature_scores.interest == 0.5
    assert by_id["one"].reason_codes == (
        "SHARED_INTEREST_ARTIFICIAL_INTELLIGENCE",
        "INTENT_MATCH_COLLABORATION",
    )
    assert "SHARED_INTEREST_PYTHON" in by_id["two"].reason_codes
    assert all(1 <= len(x.reason_codes) <= 3 for x in result.recommendations)


def test_complete_cold_start_returns_empty_scored_result():
    viewer = ViewerFeatures("viewer-1")
    result = rank_candidates(
        viewer,
        [CandidateFeatures("a"), CandidateFeatures("b")],
        ranking_date=FIXED_DATE,
    )
    assert result.result_status == "COLD_START_NEEDS_INPUT"
    assert result.ranking_mode == "COLD_START"
    assert result.recommendations == ()


def test_no_eligible_candidates_returns_empty_result():
    viewer = ViewerFeatures("viewer-1", frozenset({"ai"}), "collaboration")
    result = rank_candidates(
        viewer,
        [CandidateFeatures("blocked", frozenset({"ai"}), 1.0, 0.8, 0.9, eligible=False)],
        ranking_date=FIXED_DATE,
    )
    assert result.result_status == "NO_ELIGIBLE_CANDIDATES"
    assert result.recommendations == ()


def test_ineligible_candidate_is_never_returned():
    viewer = ViewerFeatures("viewer-1", frozenset({"ai"}), "collaboration")
    candidates = [
        CandidateFeatures(
            "allowed", frozenset({"ai"}), 1.0, 0.8, 0.9,
            interest_labels={"ai": "artificial-intelligence"},
        ),
        CandidateFeatures(
            "blocked", frozenset({"ai"}), 1.0, 1.0, 1.0,
            eligible=False,
            interest_labels={"ai": "artificial-intelligence"},
        ),
    ]
    result = rank_candidates(viewer, candidates, ranking_date=FIXED_DATE)
    assert [x.candidate_id for x in result.recommendations] == ["allowed"]


def test_exact_score_tie_uses_repeatable_hash_order():
    viewer = ViewerFeatures("viewer-1", frozenset({"ai"}), "collaboration")
    a = CandidateFeatures("a", frozenset({"ai"}), 1.0, 0.8, 0.9,
                          interest_labels={"ai": "artificial-intelligence"})
    b = CandidateFeatures("b", frozenset({"ai"}), 1.0, 0.8, 0.9,
                          interest_labels={"ai": "artificial-intelligence"})
    first = rank_candidates(viewer, [a, b], ranking_date=FIXED_DATE)
    second = rank_candidates(viewer, [b, a], ranking_date=FIXED_DATE)
    assert [x.candidate_id for x in first.recommendations] == [x.candidate_id for x in second.recommendations]
    assert first.recommendations[0].relevance_score == first.recommendations[1].relevance_score


def test_missing_optional_data_renormalizes_and_score_is_clamped():
    viewer = ViewerFeatures("viewer-1", frozenset({"ai"}), "collaboration")
    candidate = CandidateFeatures(
        "candidate", frozenset({"ai"}), 1.0, 0.8, None,
        interest_labels={"ai": "artificial-intelligence"},
    )
    result = rank_candidates(viewer, [candidate], ranking_date=FIXED_DATE)
    item = result.recommendations[0]
    assert item.feature_scores.freshness is None
    assert 0.0 <= item.relevance_score <= 1.0


def test_no_shared_interest_gets_zero_interest_score_but_needs_other_reason():
    viewer = ViewerFeatures("viewer-1", frozenset({"ai", "python"}), "collaboration")
    candidate = CandidateFeatures(
        "candidate", frozenset({"music"}), 1.0, 0.8, None,
        intent_reason_code="INTENT_COMPATIBLE_COLLABORATION",
    )
    result = rank_candidates(viewer, [candidate], ranking_date=FIXED_DATE)
    assert result.recommendations[0].feature_scores.interest == 0.0
    assert result.recommendations[0].reason_codes == ("INTENT_COMPATIBLE_COLLABORATION",)


def test_candidate_without_any_factual_reason_is_not_returned():
    viewer = ViewerFeatures("viewer-1", frozenset({"ai"}), "collaboration")
    candidate = CandidateFeatures("candidate", frozenset({"music"}), None, 1.0, 1.0)
    result = rank_candidates(viewer, [candidate], ranking_date=FIXED_DATE)
    assert result.result_status == "NO_EXPLAINABLE_MATCHES"
    assert result.recommendations == ()


def test_reason_codes_are_limited_to_three_and_derived_from_shared_facts():
    viewer = ViewerFeatures("viewer-1", frozenset({"a", "b", "c", "d"}), "collaboration")
    candidate = CandidateFeatures(
        "candidate", frozenset({"a", "b", "c", "d"}), 1.0, 1.0, 1.0,
        interest_labels={"a": "distributed-systems", "b": "python", "c": "databases", "d": "machine-learning"},
        intent_reason_code="INTENT_MATCH_COLLABORATION",
    )
    result = rank_candidates(viewer, [candidate], ranking_date=FIXED_DATE)
    codes = result.recommendations[0].reason_codes
    assert len(codes) == 3
    assert codes == (
        "SHARED_INTEREST_DATABASES",
        "SHARED_INTEREST_DISTRIBUTED_SYSTEMS",
        "SHARED_INTEREST_MACHINE_LEARNING",
    )


def test_model_rule_version_hash_is_sha256_and_deterministic():
    viewer = ViewerFeatures("viewer-1", frozenset({"ai"}), "collaboration")
    candidate = CandidateFeatures(
        "candidate", frozenset({"ai"}), 1.0, 0.8, 0.9,
        interest_labels={"ai": "artificial-intelligence"},
    )
    first = rank_candidates(viewer, [candidate], ranking_date=FIXED_DATE)
    second = rank_candidates(viewer, [candidate], ranking_date=FIXED_DATE)
    assert re.fullmatch(r"[0-9a-f]{64}", first.model_rule_version_hash)
    assert first.model_rule_version_hash == second.model_rule_version_hash


def test_diversity_adjustment_is_a_signed_score_delta():
    viewer = ViewerFeatures("viewer-1", frozenset({"ai"}), "collaboration")
    candidate = CandidateFeatures(
        "candidate", frozenset({"ai"}), 1.0, 1.0, 1.0,
        redundancy_penalty=0.5,
        interest_labels={"ai": "artificial-intelligence"},
    )
    result = rank_candidates(viewer, [candidate], ranking_date=FIXED_DATE)
    assert result.recommendations[0].feature_scores.diversity_adjustment == -0.05
    assert 0.0 <= result.recommendations[0].relevance_score <= 1.0


def test_model_rule_hash_changes_when_active_rule_configuration_changes():
    viewer = ViewerFeatures("viewer-1", frozenset({"ai"}), "collaboration")
    candidate = CandidateFeatures(
        "candidate", frozenset({"ai"}), 1.0, 0.8, 0.9,
        interest_labels={"ai": "artificial-intelligence"},
    )
    fresh_enabled = rank_candidates(
        viewer, [candidate], ranking_date=FIXED_DATE,
        rule_config={"freshness_enabled": True, "freshness_half_life_days": 7},
    )
    fresh_disabled = rank_candidates(
        viewer, [candidate], ranking_date=FIXED_DATE,
        rule_config={"freshness_enabled": False, "freshness_half_life_days": None},
    )
    assert fresh_enabled.model_rule_version_hash != fresh_disabled.model_rule_version_hash
