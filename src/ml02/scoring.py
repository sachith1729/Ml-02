from __future__ import annotations

from dataclasses import dataclass
from typing import Collection, Mapping, Optional

from .models import FeatureScores
from .features import validate_unit_score


@dataclass(frozen=True)
class ScoringWeights:
    interest: float = 0.45
    intent: float = 0.25
    profile: float = 0.15
    freshness: float = 0.15
    redundancy_lambda: float = 0.10

    def __post_init__(self) -> None:
        values = (self.interest, self.intent, self.profile, self.freshness)
        if any(v < 0 for v in values):
            raise ValueError("feature weights cannot be negative")
        if abs(sum(values) - 1.0) > 1e-9:
            raise ValueError("feature weights must sum to 1.0")
        if not 0 <= self.redundancy_lambda <= 1:
            raise ValueError("redundancy_lambda must be between 0 and 1")


DEFAULT_WEIGHTS = ScoringWeights()

_FEATURE_NAMES = ("interest", "intent", "profile", "freshness")


def calculate_score(
    features: FeatureScores,
    weights: ScoringWeights = DEFAULT_WEIGHTS,
    *,
    enabled_features: Collection[str] | None = None,
) -> Optional[float]:
    """Calculate a clamped weighted score.

    In the ML-02 ranking pipeline, callers MUST pass the request-level
    ``enabled_features`` mask computed once for the entire eligible candidate
    pool. This ensures every candidate in one request is scored with the same
    feature set and the same denominator.

    ``enabled_features=None`` is retained for backwards compatibility with
    isolated/legacy callers; it uses the old available-feature normalization.
    Do not use that mode to compare candidates within a ranking request.
    """
    available: Mapping[str, Optional[float]] = {
        "interest": features.interest,
        "intent": features.intent,
        "profile": features.profile,
        "freshness": features.freshness,
    }
    configured = {
        "interest": weights.interest,
        "intent": weights.intent,
        "profile": weights.profile,
        "freshness": weights.freshness,
    }

    if enabled_features is None:
        selected = tuple(
            name for name in _FEATURE_NAMES
            if validate_unit_score(available[name], name) is not None
        )
    else:
        selected_set = set(enabled_features)
        unknown = selected_set.difference(_FEATURE_NAMES)
        if unknown:
            raise ValueError(f"unknown enabled features: {sorted(unknown)}")
        selected = tuple(name for name in _FEATURE_NAMES if name in selected_set)

    numerator = 0.0
    denominator = 0.0
    for name in selected:
        validated = validate_unit_score(available[name], name)
        if validated is None:
            raise ValueError(
                f"enabled feature '{name}' is missing; "
                "compute one request-level feature mask before scoring candidates"
            )
        weight = configured[name]
        numerator += weight * validated
        denominator += weight

    if denominator == 0:
        return None

    adjustment = features.diversity_adjustment
    if isinstance(adjustment, bool) or not isinstance(adjustment, (int, float)):
        raise TypeError("diversity_adjustment must be numeric")
    adjustment = float(adjustment)
    if adjustment > 0 or adjustment < -weights.redundancy_lambda:
        raise ValueError("diversity_adjustment must be between -redundancy_lambda and 0")

    score = (numerator / denominator) + adjustment
    return round(min(1.0, max(0.0, score)), 6)
