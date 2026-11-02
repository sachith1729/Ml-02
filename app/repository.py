from __future__ import annotations

from typing import Any
from uuid import UUID

from psycopg import Connection
from psycopg.types.json import Jsonb

from app.config import ENABLE_MOCK_FRESHNESS, FRESHNESS_HALF_LIFE_DAYS
from ml02.features import freshness_from_timestamp, normalize_profile_completeness
from ml02.models import CandidateFeatures, ViewerFeatures
from ml02.ranker import rank_candidates


class ViewerNotFoundError(Exception):
    pass


class ViewerNotEligibleError(Exception):
    pass


def _get_active_intents(conn: Connection, user_ids: list[UUID]) -> dict[str, str]:
    if not user_ids:
        return {}
    rows = conn.execute(
        """
        SELECT DISTINCT ON (user_id)
               user_id::text AS user_id, intent_code
        FROM core.connection_intents
        WHERE user_id = ANY(%s)
          AND status = 'active'
          AND visibility = 'visible'
        ORDER BY user_id, updated_at DESC, created_at DESC
        """,
        (user_ids,),
    ).fetchall()
    return {row["user_id"]: row["intent_code"] for row in rows}


def load_ranking_input(
    conn: Connection,
    viewer_id: UUID,
    *,
    mode: str = "default",
) -> tuple[ViewerFeatures, list[CandidateFeatures], dict[str, Any]]:
    """Load viewer/candidate features from mock PostgreSQL tables.

    The candidate-pool query is a development simulation of ML-01. In production,
    replace it with the approved ML-01 service/contract; do not move policy ownership
    into ML-02.
    """
    # Use the database clock so activity timestamps and ranking share one time source.
    now = conn.execute("SELECT transaction_timestamp() AS db_now").fetchone()["db_now"]
    viewer_row = conn.execute(
        """
        SELECT u.id, u.status, u.contact_verification_status,
               u.age_eligibility_status, p.visibility_status
        FROM core.users u
        LEFT JOIN core.profiles p ON p.user_id = u.id
        WHERE u.id = %s
        """,
        (viewer_id,),
    ).fetchone()
    if viewer_row is None:
        raise ViewerNotFoundError(f"Viewer {viewer_id} was not found")
    if (
        viewer_row["status"] != "active"
        or viewer_row["contact_verification_status"] != "verified"
        or viewer_row["age_eligibility_status"] != "eligible"
    ):
        raise ViewerNotEligibleError("Viewer does not meet the mock discovery access requirements")

    # Mock ML-01 eligibility filter. All hard exclusions are resolved before ranking.
    candidate_rows = conn.execute(
        """
        SELECT u.id AS candidate_id,
               p.profile_completeness
        FROM core.users u
        JOIN core.profiles p ON p.user_id = u.id
        WHERE u.id <> %s
          AND u.status = 'active'
          AND u.contact_verification_status = 'verified'
          AND u.age_eligibility_status = 'eligible'
          AND u.deleted_at IS NULL
          AND p.deleted_at IS NULL
          AND p.visibility_status = 'visible'
          AND NOT EXISTS (
              SELECT 1 FROM core.blocks b
              WHERE b.removed_at IS NULL
                AND ((b.blocker_user_id = %s AND b.blocked_user_id = u.id)
                  OR (b.blocker_user_id = u.id AND b.blocked_user_id = %s))
          )
          AND NOT EXISTS (
              SELECT 1 FROM core.connections c
              WHERE c.status = 'active'
                AND c.user_low_id = LEAST(%s, u.id)
                AND c.user_high_id = GREATEST(%s, u.id)
          )
          AND NOT EXISTS (
              SELECT 1 FROM core.connection_requests cr
              WHERE LEAST(cr.sender_user_id, cr.recipient_user_id) = LEAST(%s, u.id)
                AND GREATEST(cr.sender_user_id, cr.recipient_user_id) = GREATEST(%s, u.id)
                AND ((cr.status = 'pending' AND cr.expires_at > %s)
                  OR (cr.cooldown_until IS NOT NULL AND cr.cooldown_until > %s))
          )
          AND NOT EXISTS (
              SELECT 1 FROM core.discovery_dismissals d
              WHERE d.viewer_user_id = %s
                AND d.candidate_user_id = u.id
                AND (d.scope = 'all' OR d.scope = %s)
                AND (d.expires_at IS NULL OR d.expires_at > %s)
          )
        ORDER BY u.id
        """,
        (
            viewer_id,
            viewer_id, viewer_id,
            viewer_id, viewer_id,
            viewer_id, viewer_id, now, now,
            viewer_id, mode, now,
        ),
    ).fetchall()

    candidate_ids = [row["candidate_id"] for row in candidate_rows]
    all_ids = [viewer_id, *candidate_ids]
    id_strings = [str(value) for value in all_ids]

    interest_rows = conn.execute(
        """
        SELECT ui.user_id::text AS user_id,
               ui.interest_id::text AS interest_id,
               i.label,
               i.slug
        FROM core.user_interests ui
        JOIN core.interests i ON i.id = ui.interest_id
        WHERE ui.user_id = ANY(%s)
          AND i.status = 'active'
        ORDER BY i.label
        """,
        (all_ids,),
    ).fetchall()
    interest_ids_by_user: dict[str, set[str]] = {key: set() for key in id_strings}
    labels_by_user: dict[str, dict[str, str]] = {key: {} for key in id_strings}
    slugs_by_user: dict[str, dict[str, str]] = {key: {} for key in id_strings}
    for row in interest_rows:
        uid = row["user_id"]
        interest_id = row["interest_id"]
        interest_ids_by_user.setdefault(uid, set()).add(interest_id)
        labels_by_user.setdefault(uid, {})[interest_id] = row["label"]
        slugs_by_user.setdefault(uid, {})[interest_id] = row["slug"]

    intents = _get_active_intents(conn, all_ids)
    viewer_intent = intents.get(str(viewer_id))

    compatibility: dict[str, tuple[float, str | None]] = {}
    candidate_intent_codes = sorted({intents[str(cid)] for cid in candidate_ids if str(cid) in intents})
    if viewer_intent and candidate_intent_codes:
        rows = conn.execute(
            """
            SELECT candidate_intent_code, compatibility_score, reason_code
            FROM core.mock_intent_compatibility
            WHERE viewer_intent_code = %s
              AND candidate_intent_code = ANY(%s)
              AND enabled = TRUE
            """,
            (viewer_intent, candidate_intent_codes),
        ).fetchall()
        compatibility = {
            row["candidate_intent_code"]: (float(row["compatibility_score"]), row["reason_code"])
            for row in rows
        }

    freshness_by_user: dict[str, float | None] = {str(cid): None for cid in candidate_ids}
    if ENABLE_MOCK_FRESHNESS and candidate_ids:
        activity_rows = conn.execute(
            """
            SELECT user_id::text AS user_id, last_active_at
            FROM core.mock_activity
            WHERE user_id = ANY(%s)
            """,
            (candidate_ids,),
        ).fetchall()
        for row in activity_rows:
            freshness_by_user[row["user_id"]] = freshness_from_timestamp(
                row["last_active_at"],
                now=now,
                half_life_days=FRESHNESS_HALF_LIFE_DAYS,
            )

    viewer = ViewerFeatures(
        user_id=str(viewer_id),
        interest_ids=frozenset(interest_ids_by_user.get(str(viewer_id), set())),
        intent_code=viewer_intent,
    )

    candidates: list[CandidateFeatures] = []
    for row in candidate_rows:
        candidate_id = row["candidate_id"]
        candidate_key = str(candidate_id)
        candidate_intent = intents.get(candidate_key)
        intent_pair = compatibility.get(candidate_intent) if candidate_intent else None
        completeness = normalize_profile_completeness(row["profile_completeness"])
        candidates.append(
            CandidateFeatures(
                candidate_id=candidate_key,
                interest_ids=frozenset(interest_ids_by_user.get(candidate_key, set())),
                intent_score=intent_pair[0] if intent_pair else None,
                profile_completeness=completeness,
                freshness_score=freshness_by_user.get(candidate_key),
                redundancy_penalty=0.0,  # No approved diversity formula/input yet.
                eligible=True,  # The mock ML-01 query already applied hard filters.
                interest_labels=slugs_by_user.get(candidate_key, {}),
                intent_reason_code=intent_pair[1] if intent_pair else None,
            )
        )

    debug_input = {
        "viewer": {
            "user_id": str(viewer_id),
            "interest_ids": sorted(viewer.interest_ids),
            "interest_labels": labels_by_user.get(str(viewer_id), {}),
            "intent_code": viewer.intent_code,
        },
        "candidate_pool_source": "mock_ML01_SQL_filter",
        "candidate_count": len(candidates),
        "candidates": [
            {
                "candidate_id": c.candidate_id,
                "interest_ids": sorted(c.interest_ids),
                "interest_labels": labels_by_user.get(c.candidate_id, {}),
                "interest_reason_slugs": slugs_by_user.get(c.candidate_id, {}),
                "intent_code": intents.get(c.candidate_id),
                "intent_score": c.intent_score,
                "profile_completeness": c.profile_completeness,
                "freshness_score": c.freshness_score,
                "redundancy_penalty": c.redundancy_penalty,
                "eligible": c.eligible,
            }
            for c in candidates
        ],
        "feature_configuration": {
            "freshness_enabled": ENABLE_MOCK_FRESHNESS,
            "freshness_source": "core.mock_activity (DEV-ONLY)",
            "freshness_half_life_days": FRESHNESS_HALF_LIFE_DAYS if ENABLE_MOCK_FRESHNESS else None,
            "intent_mapping_source": "core.mock_intent_compatibility (DEV-ONLY)",
            "redundancy_enabled": False,
        },
    }
    return viewer, candidates, debug_input


def persist_ranking_result(
    conn: Connection,
    *,
    viewer_id: UUID,
    mode: str,
    ranking_result: Any,
) -> UUID:
    run_row = conn.execute(
        """
        INSERT INTO ml02.ranking_runs
            (viewer_user_id, result_status, ranking_mode, personalized, model_version,
             model_rule_version_hash, request_mode)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING run_id
        """,
        (
            viewer_id,
            ranking_result.result_status,
            ranking_result.ranking_mode,
            ranking_result.personalized,
            ranking_result.model_version,
            ranking_result.model_rule_version_hash,
            mode,
        ),
    ).fetchone()
    run_id = run_row["run_id"]

    for item in ranking_result.recommendations:
        conn.execute(
            """
            INSERT INTO ml02.ranking_results
                (run_id, candidate_user_id, rank_position, relevance_score,
                 feature_scores, reason_codes, tie_break_hash)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                run_id,
                UUID(item.candidate_id),
                item.rank,
                item.relevance_score,
                Jsonb({
                    "interest": item.feature_scores.interest,
                    "intent": item.feature_scores.intent,
                    "profile": item.feature_scores.profile,
                    "freshness": item.feature_scores.freshness,
                    "diversity_adjustment": item.feature_scores.diversity_adjustment,
                }),
                list(item.reason_codes),
                item.tie_break_key,
            ),
        )
    return run_id


def load_saved_run(conn: Connection, run_id: UUID) -> dict[str, Any] | None:
    run = conn.execute(
        "SELECT * FROM ml02.ranking_runs WHERE run_id = %s",
        (run_id,),
    ).fetchone()
    if run is None:
        return None
    rows = conn.execute(
        """
        SELECT candidate_user_id, rank_position, relevance_score,
               feature_scores, reason_codes, tie_break_hash
        FROM ml02.ranking_results
        WHERE run_id = %s
        ORDER BY rank_position
        """,
        (run_id,),
    ).fetchall()
    return {
        "run_id": str(run["run_id"]),
        "viewer_user_id": str(run["viewer_user_id"]),
        "result_status": run["result_status"],
        "ranking_mode": run["ranking_mode"],
        "personalized": run["personalized"],
        "model_version": run["model_version"],
        "model_rule_version_hash": run["model_rule_version_hash"],
        "request_mode": run["request_mode"],
        "created_at": run["created_at"].isoformat(),
        "recommendations": [
            {
                "candidate_id": str(row["candidate_user_id"]),
                "rank_position": row["rank_position"],
                "composite_relevance_score": float(row["relevance_score"]),
                "feature_sub_scores": {
                    "interest": row["feature_scores"].get("interest"),
                    "intent": row["feature_scores"].get("intent"),
                    "profile": row["feature_scores"].get("profile"),
                    "freshness": row["feature_scores"].get("freshness"),
                },
                "diversity_adjustment": row["feature_scores"].get("diversity_adjustment", 0.0),
                "reason_codes": row["reason_codes"],
            }
            for row in rows
        ],
    }
