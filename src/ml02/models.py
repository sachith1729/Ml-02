from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Optional, FrozenSet


@dataclass(frozen=True)
class ViewerFeatures:
    user_id: str
    interest_ids: FrozenSet[str] = frozenset()
    intent_code: Optional[str] = None


@dataclass(frozen=True)
class CandidateFeatures:
    candidate_id: str
    interest_ids: FrozenSet[str] = frozenset()
    # 0..1 compatibility score produced by a product-approved intent mapping.
    # None means the feature is unavailable, not a mismatch.
    intent_score: Optional[float] = None
    # Normalized ratio 0..1. Convert SQL SMALLINT (0..100) in the repository layer.
    profile_completeness: Optional[float] = None
    # Normalized feature 0..1. None until a trusted activity source/policy exists.
    freshness_score: Optional[float] = None
    # 0..1 raw redundancy penalty from a separately approved diversity layer.
    redundancy_penalty: float = 0.0
    # ML-01 is authoritative. False candidates are defensively discarded.
    eligible: bool = True
    # Active taxonomy slugs for interests visible to both users.
    interest_labels: Mapping[str, str] = field(default_factory=dict)
    # Factual code from approved intent compatibility and visible intent records.
    intent_reason_code: Optional[str] = None


@dataclass(frozen=True)
class FeatureScores:
    interest: Optional[float]
    intent: Optional[float]
    profile: Optional[float]
    freshness: Optional[float]
    # Signed score delta: zero or negative, e.g. -0.02.
    diversity_adjustment: float


@dataclass(frozen=True)
class RankedCandidate:
    candidate_id: str
    rank: int
    relevance_score: float
    feature_scores: FeatureScores
    reason_codes: tuple[str, ...]
    tie_break_key: str


@dataclass(frozen=True)
class RankingResult:
    result_status: str
    ranking_mode: str
    personalized: bool
    model_version: str
    model_rule_version_hash: str
    recommendations: tuple[RankedCandidate, ...]
