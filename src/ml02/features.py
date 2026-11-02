from __future__ import annotations

from datetime import datetime, timezone
import math
from typing import Iterable, Optional


def jaccard_similarity(viewer_interests: Iterable[str], candidate_interests: Iterable[str]) -> Optional[float]:
    """Return Jaccard similarity. None means the viewer has no interest signal."""
    viewer = set(viewer_interests)
    candidate = set(candidate_interests)
    if not viewer:
        return None
    union = viewer | candidate
    if not union:
        return None
    return len(viewer & candidate) / len(union)


def normalize_profile_completeness(percent: Optional[int]) -> Optional[float]:
    """Convert core.profiles.profile_completeness (0..100) to (0..1)."""
    if percent is None:
        return None
    if isinstance(percent, bool) or not isinstance(percent, int):
        raise TypeError("profile completeness must be an integer percentage")
    if not 0 <= percent <= 100:
        raise ValueError("profile completeness must be between 0 and 100")
    return percent / 100.0


def freshness_from_timestamp(
    last_active_at: Optional[datetime],
    *,
    now: datetime,
    half_life_days: float,
) -> Optional[float]:
    """Example exponential freshness transform; requires approved source and half-life.

    Do not call until the database source and product half-life are approved.
    A timestamp in the future is rejected rather than rewarded.
    """
    if last_active_at is None:
        return None
    if half_life_days <= 0 or not math.isfinite(half_life_days):
        raise ValueError("half_life_days must be finite and greater than zero")
    if last_active_at.tzinfo is None or now.tzinfo is None:
        raise ValueError("timestamps must be timezone-aware")
    active = last_active_at.astimezone(timezone.utc)
    current = now.astimezone(timezone.utc)
    age_seconds = (current - active).total_seconds()
    if age_seconds < 0:
        raise ValueError("last_active_at cannot be in the future")
    age_days = age_seconds / 86400.0
    return 0.5 ** (age_days / half_life_days)


def validate_unit_score(value: Optional[float], field_name: str) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field_name} must be numeric or None")
    value = float(value)
    if not math.isfinite(value) or not 0.0 <= value <= 1.0:
        raise ValueError(f"{field_name} must be between 0 and 1")
    return value
