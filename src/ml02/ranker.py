from __future__ import annotations

from datetime import date, datetime, timezone
from hashlib import sha256
import re
from typing import Any, Iterable, Mapping, Optional

from . import MODEL_VERSION
from .features import jaccard_similarity, validate_unit_score
from .models import (
    CandidateFeatures,
    FeatureScores,
    RankedCandidate,
    RankingResult,
    ViewerFeatures,
)
from .scoring import DEFAULT_WEIGHTS, ScoringWeights, calculate_score
from .versioning import build_model_rule_version_hash


_MISSING_FEATURE_POLICY = "REQUEST_LEVEL_COMPLETE_CASE_V1"


def _stable_tie_key(viewer_id: str, candidate_id: str, ranking_date: date) -> str:
    """Stable tie-break from the agreed rule: viewer, candidate and UTC date."""
    raw = f"{viewer_id}|{candidate_id}|{ranking_date.isoformat()}".encode("utf-8")
    return sha256(raw).hexdigest()


def _reason_codes(
    viewer: ViewerFeatures,
    candidate: CandidateFeatures,
    *,
    include_intent_reason: bool,
) -> tuple[str, ...]:
    """Create 1-3 deterministic codes only from visible, shared facts.

    Interest IDs must already have passed repository active/visible filtering.
    Intent reason codes are emitted only when the viewer has an intent and
    the intent feature is enabled for the whole request.
    """
    shared = sorted(set(viewer.interest_ids) & set(candidate.interest_ids))
    interest_codes: set[str] = set()
    for interest_id in shared:
        slug = candidate.interest_labels.get(interest_id)
        if not slug:
            continue
        normalized = re.sub(r"[^A-Za-z0-9]+", "_", slug).strip("_").upper()
        if normalized:
            interest_codes.add(f"SHARED_INTEREST_{normalized}")

    codes = sorted(interest_codes)
    if (
        include_intent_reason
        and viewer.intent_code is not None
        and candidate.intent_score is not None
        and candidate.intent_score > 0
        and candidate.intent_reason_code
    ):
        # Accept only deterministic uppercase reason-code tokens, not arbitrary text.
        intent_code = candidate.intent_reason_code.strip().upper()
        if re.fullmatch(r"[A-Z][A-Z0-9_]{1,79}", intent_code) and intent_code not in codes:
            codes.append(intent_code)

    return tuple(codes[:3])


def _empty_result(
    *,
    status: str,
    ranking_mode: str,
    personalized: bool,
    model_version: str,
    weights: ScoringWeights,
    rule_config: Mapping[str, Any] | None,
) -> RankingResult:
    return RankingResult(
        result_status=status,
        ranking_mode=ranking_mode,
        personalized=personalized,
        model_version=model_version,
        model_rule_version_hash=build_model_rule_version_hash(
            model_version, weights, rule_config
        ),
        recommendations=(),
    )


def _pool_has_complete_score(
    candidates: list[CandidateFeatures],
    attribute: str,
    feature_name: str,
) -> bool:
    """True only when every eligible candidate has a valid 0..1 value."""
    for candidate in candidates:
        value = getattr(candidate, attribute)
        if validate_unit_score(value, feature_name) is None:
            return False
    return True


def rank_candidates(
    viewer: ViewerFeatures,
    candidates: Iterable[CandidateFeatures],
    *,
    ranking_date: Optional[date] = None,
    weights: ScoringWeights = DEFAULT_WEIGHTS,
    model_version: str = MODEL_VERSION,
    rule_config: Mapping[str, Any] | None = None,
) -> RankingResult:
    """Rank ML-01 candidates using one consistent feature mask per request.

    Missing optional feature policy:
    - If any eligible candidate lacks intent compatibility, intent is disabled
      for every candidate in this request.
    - If any eligible candidate lacks profile completeness, profile is disabled
      for every candidate in this request.
    - If any eligible candidate lacks freshness, freshness is disabled for
      every candidate in this request.
    - Interest is enabled only when the viewer has at least one visible interest.
      A candidate with no interests then receives a valid interest score of 0.
    This avoids candidate-specific weight renormalization, which can reward a
    candidate simply because one of its fields is missing.
    """
    ranking_date = ranking_date or datetime.now(timezone.utc).date()
    eligible_candidates = [c for c in candidates if c.eligible]

    effective_rule_config: dict[str, Any] = dict(rule_config or {})
    effective_rule_config["missing_feature_policy"] = _MISSING_FEATURE_POLICY

    if not eligible_candidates:
        effective_rule_config["enabled_features"] = []
        return _empty_result(
            status="NO_ELIGIBLE_CANDIDATES",
            ranking_mode="EMPTY",
            personalized=False,
            model_version=model_version,
            weights=weights,
            rule_config=effective_rule_config,
        )

    if not viewer.interest_ids and not viewer.intent_code:
        effective_rule_config["enabled_features"] = []
        return _empty_result(
            status="COLD_START_NEEDS_INPUT",
            ranking_mode="COLD_START",
            personalized=False,
            model_version=model_version,
            weights=weights,
            rule_config=effective_rule_config,
        )

    interest_enabled = bool(viewer.interest_ids) and weights.interest > 0
    intent_enabled = (
        viewer.intent_code is not None
        and weights.intent > 0
        and _pool_has_complete_score(eligible_candidates, "intent_score", "intent_score")
    )
    profile_enabled = (
        weights.profile > 0
        and _pool_has_complete_score(
            eligible_candidates, "profile_completeness", "profile_completeness"
        )
    )
    freshness_enabled = (
        weights.freshness > 0
        and _pool_has_complete_score(
            eligible_candidates, "freshness_score", "freshness_score"
        )
    )

    enabled_features = tuple(
        name
        for name, enabled in (
            ("interest", interest_enabled),
            ("intent", intent_enabled),
            ("profile", profile_enabled),
            ("freshness", freshness_enabled),
        )
        if enabled
    )

    # Profile completeness and freshness are supporting features, not
    # personalization signals by themselves. At least one viewer-specific
    # feature (interest or intent) must be available.
    if not interest_enabled and not intent_enabled:
        effective_rule_config["enabled_features"] = list(enabled_features)
        return _empty_result(
            status="NO_PERSONALIZATION_SIGNALS_AVAILABLE",
            ranking_mode="EMPTY",
            personalized=False,
            model_version=model_version,
            weights=weights,
            rule_config=effective_rule_config,
        )

    effective_rule_config["enabled_features"] = list(enabled_features)

    scored: list[
        tuple[float, str, CandidateFeatures, FeatureScores, tuple[str, ...]]
    ] = []

    for candidate in eligible_candidates:
        interest_score = (
            jaccard_similarity(viewer.interest_ids, candidate.interest_ids)
            if interest_enabled
            else None
        )
        intent_score = (
            validate_unit_score(candidate.intent_score, "intent_score")
            if intent_enabled
            else None
        )
        profile_score = (
            validate_unit_score(candidate.profile_completeness, "profile_completeness")
            if profile_enabled
            else None
        )
        freshness_score = (
            validate_unit_score(candidate.freshness_score, "freshness_score")
            if freshness_enabled
            else None
        )

        raw_diversity_penalty = validate_unit_score(
            candidate.redundancy_penalty, "redundancy_penalty"
        )
        if raw_diversity_penalty is None:
            raise ValueError("redundancy_penalty must be present for every candidate")

        diversity_adjustment = (
            0.0
            if raw_diversity_penalty == 0
            else -weights.redundancy_lambda * raw_diversity_penalty
        )

        feature_scores = FeatureScores(
            interest=interest_score,
            intent=intent_score,
            profile=profile_score,
            freshness=freshness_score,
            diversity_adjustment=round(diversity_adjustment, 6),
        )

        score = calculate_score(
            feature_scores,
            weights,
            enabled_features=enabled_features,
        )
        if score is None:
            continue

        reasons = _reason_codes(
            viewer,
            candidate,
            include_intent_reason=intent_enabled,
        )
        if not 1 <= len(reasons) <= 3:
            continue

        tie_key = _stable_tie_key(
            viewer.user_id, candidate.candidate_id, ranking_date
        )
        scored.append((score, tie_key, candidate, feature_scores, reasons))

    if not scored:
        return _empty_result(
            status="NO_EXPLAINABLE_MATCHES",
            ranking_mode="EMPTY",
            personalized=False,
            model_version=model_version,
            weights=weights,
            rule_config=effective_rule_config,
        )

    scored.sort(key=lambda item: (-item[0], item[1]))
    recommendations = tuple(
        RankedCandidate(
            candidate_id=candidate.candidate_id,
            rank=rank,
            relevance_score=max(0.0, min(1.0, score)),
            feature_scores=features,
            reason_codes=reasons,
            tie_break_key=tie_key,
        )
        for rank, (score, tie_key, candidate, features, reasons)
        in enumerate(scored, start=1)
    )

    return RankingResult(
        result_status="OK",
        ranking_mode="PERSONALIZED",
        personalized=True,
        model_version=model_version,
        model_rule_version_hash=build_model_rule_version_hash(
            model_version, weights, effective_rule_config
        ),
        recommendations=recommendations,
    )
