import pytest

from ml02.features import jaccard_similarity, normalize_profile_completeness


def test_jaccard_multiple_shared_interests():
    assert jaccard_similarity({"ai", "python", "dbms"}, {"ai", "python", "music"}) == pytest.approx(0.5)


def test_jaccard_single_shared_interest():
    assert jaccard_similarity({"ai", "python", "dbms"}, {"ai", "music"}) == pytest.approx(0.25)


def test_jaccard_all_interests_shared():
    assert jaccard_similarity({"ai", "python"}, {"ai", "python"}) == 1.0


def test_jaccard_no_shared_interests():
    assert jaccard_similarity({"ai"}, {"music"}) == 0.0


def test_jaccard_deduplicates_values():
    assert jaccard_similarity(["ai", "ai"], ["ai"]) == 1.0


def test_empty_viewer_interest_is_unavailable():
    assert jaccard_similarity(set(), {"ai"}) is None


def test_profile_completeness_percent_to_ratio():
    assert normalize_profile_completeness(80) == 0.8


def test_profile_completeness_out_of_range_rejected():
    with pytest.raises(ValueError):
        normalize_profile_completeness(120)
