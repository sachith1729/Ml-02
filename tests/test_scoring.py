import pytest

from ml02.models import FeatureScores
from ml02.scoring import calculate_score


def test_full_weighted_score_without_penalty():
    features = FeatureScores(0.5, 1.0, 0.8, 0.9, 0.0)
    assert calculate_score(features) == pytest.approx(0.73)


def test_missing_freshness_renormalizes_available_weights():
    features = FeatureScores(0.5, 1.0, 0.8, None, 0.0)
    expected = (0.45 * 0.5 + 0.25 * 1.0 + 0.15 * 0.8) / 0.85
    assert calculate_score(features) == pytest.approx(round(expected, 6))


def test_no_available_features_returns_none():
    features = FeatureScores(None, None, None, None, 0.0)
    assert calculate_score(features) is None


def test_diversity_adjustment_is_bounded_and_applied():
    features = FeatureScores(1.0, 1.0, 1.0, 1.0, -0.05)
    assert calculate_score(features) == pytest.approx(0.95)


def test_invalid_score_rejected():
    features = FeatureScores(1.2, 1.0, 1.0, 1.0, 0.0)
    with pytest.raises(ValueError):
        calculate_score(features)


def test_score_clamps_at_one_and_zero():
    assert calculate_score(FeatureScores(1.0, 1.0, 1.0, 1.0, 0.0)) == 1.0
    assert calculate_score(FeatureScores(0.0, 0.0, 0.0, 0.0, -0.1)) == 0.0


def test_positive_diversity_adjustment_rejected():
    with pytest.raises(ValueError):
        calculate_score(FeatureScores(1.0, 1.0, 1.0, 1.0, 0.01))
