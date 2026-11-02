from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
import json
from typing import Any, Mapping

from .scoring import DEFAULT_WEIGHTS, ScoringWeights

REASON_CODE_VERSION = "reason-codes-v1"
TIE_BREAK_VERSION = "sha256-viewer-candidate-utc-date-v1"
SCORING_RULE_VERSION = "mals-rank-available-weight-renormalization-v1"


def build_model_rule_version_hash(
    model_version: str,
    weights: ScoringWeights = DEFAULT_WEIGHTS,
    rule_config: Mapping[str, Any] | None = None,
) -> str:
    """Return a reproducible SHA-256 hash of active ranking rules/config."""
    rule_manifest = {
        "model_version": model_version,
        "scoring_rule_version": SCORING_RULE_VERSION,
        "reason_code_version": REASON_CODE_VERSION,
        "tie_break_version": TIE_BREAK_VERSION,
        "interest_similarity": "jaccard-over-unique-active-interest-ids-v1",
        "profile_normalization": "percent-divided-by-100-v1",
        "freshness_transform": "exponential-half-life-v1",
        "weights": asdict(weights),
        "rule_config": dict(rule_config or {}),
        "score_bounds": [0.0, 1.0],
        "reason_code_count": [1, 3],
        "missing_feature_policy": "renormalize_available_feature_weights",
        "no_explainable_reason_policy": "exclude_candidate",
    }
    canonical = json.dumps(rule_manifest, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(canonical.encode("utf-8")).hexdigest()
