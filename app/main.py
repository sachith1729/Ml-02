from __future__ import annotations

from typing import Any
from uuid import UUID

import psycopg
from fastapi import FastAPI, HTTPException, Query

from app.database import get_connection
from app.config import (
    ENABLE_MOCK_FRESHNESS,
    FRESHNESS_HALF_LIFE_DAYS,
    MODEL_VERSION_OVERRIDE,
)
from app.repository import (
    ViewerNotEligibleError,
    ViewerNotFoundError,
    load_ranking_input,
    load_saved_run,
    persist_ranking_result,
)
from ml02.ranker import rank_candidates
from ml02 import MODEL_VERSION

app = FastAPI(
    title="ML-02 Explainable Discovery Ranking",
    version="0.3.0",
    description=(
        "Development prototype: mock PostgreSQL input tables → ML-02 ranking engine "
        "→ persisted ranked output. The SQL candidate filter simulates ML-01 only."
    ),
)


@app.get("/health")
def health() -> dict[str, str]:
    try:
        with get_connection() as conn:
            conn.execute("SELECT 1").fetchone()
        return {"status": "ok", "service": "ml02", "database": "connected"}
    except Exception as exc:  # pragma: no cover - depends on external PostgreSQL
        raise HTTPException(status_code=503, detail="Database is unavailable") from exc


@app.get("/mock/scenarios")
def mock_scenarios() -> dict[str, Any]:
    return {
        "note": "All UUIDs below identify synthetic demo users, not real people.",
        "viewers": [
            {
                "name": "Complete profile viewer",
                "viewer_id": "00000000-0000-0000-0000-000000000101",
                "scenario": "Has AI, Python, DBMS interests and collaboration intent.",
            },
            {
                "name": "Complete cold-start viewer",
                "viewer_id": "00000000-0000-0000-0000-000000000102",
                "scenario": "No interests and no intent; ML-02 returns an empty ranked result and asks for onboarding signals.",
            },
        ],
        "candidate_fixtures": {
            "00000000-0000-0000-0000-000000000201": "Three matching interests; strong candidate.",
            "00000000-0000-0000-0000-000000000202": "Two shared interests.",
            "00000000-0000-0000-0000-000000000203": "One shared interest.",
            "00000000-0000-0000-0000-000000000204": "No shared interests; explicit mock intent compatibility.",
            "00000000-0000-0000-0000-000000000205": "No factual shared reason; correctly omitted from explainable recommendations.",
            "00000000-0000-0000-0000-000000000212": "Same feature values as candidate 201 to exercise exact score ties.",
        },
        "excluded_fixtures": {
            "00000000-0000-0000-0000-000000000206": "Blocked by viewer 101.",
            "00000000-0000-0000-0000-000000000207": "Hidden profile.",
            "00000000-0000-0000-0000-000000000208": "Already connected to viewer 101.",
            "00000000-0000-0000-0000-000000000209": "Pending connection request with viewer 101.",
            "00000000-0000-0000-0000-000000000210": "Dismissed by viewer 101.",
            "00000000-0000-0000-0000-000000000211": "Suspended account.",
        },
    }


@app.get("/debug/input/{viewer_id}")
def debug_input(
    viewer_id: UUID,
    mode: str = Query(default="default", min_length=1, max_length=40),
) -> dict[str, Any]:
    """Return the exact features extracted from mock SQL tables before ranking."""
    try:
        with get_connection() as conn:
            _, _, debug = load_ranking_input(conn, viewer_id, mode=mode)
        return debug
    except ViewerNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ViewerNotEligibleError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except psycopg.Error as exc:
        raise HTTPException(status_code=503, detail="Database query failed") from exc


@app.post("/rank/{viewer_id}")
def run_ranking(
    viewer_id: UUID,
    mode: str = Query(default="default", min_length=1, max_length=40),
    persist: bool = Query(default=True),
) -> dict[str, Any]:
    """Extract mock SQL input, execute MALS-Rank, and optionally save output tables."""
    try:
        with get_connection() as conn:
            viewer, candidates, _debug = load_ranking_input(conn, viewer_id, mode=mode)
            result = rank_candidates(
                viewer,
                candidates,
                model_version=MODEL_VERSION_OVERRIDE or MODEL_VERSION,
                rule_config={
                    "freshness_enabled": ENABLE_MOCK_FRESHNESS,
                    "freshness_half_life_days": FRESHNESS_HALF_LIFE_DAYS if ENABLE_MOCK_FRESHNESS else None,
                    "intent_compatibility_contract": "mock-intent-compatibility-v1",
                    "diversity_penalty_enabled": False,
                },
            )
            run_id = persist_ranking_result(
                conn,
                viewer_id=viewer_id,
                mode=mode,
                ranking_result=result,
            ) if persist else None
        return {
            "viewer_id": str(viewer_id),
            "result_status": result.result_status,
            "ranking_mode": result.ranking_mode,
            "model_version": result.model_version,
            "model_rule_version_hash": result.model_rule_version_hash,
            "recommendations": [
                {
                    "candidate_id": item.candidate_id,
                    "rank_position": item.rank,
                    "composite_relevance_score": max(0.0, min(1.0, item.relevance_score)),
                    "feature_sub_scores": {
                        "interest": item.feature_scores.interest,
                        "intent": item.feature_scores.intent,
                        "profile": item.feature_scores.profile,
                        "freshness": item.feature_scores.freshness,
                    },
                    "diversity_adjustment": item.feature_scores.diversity_adjustment,
                    "reason_codes": list(item.reason_codes),
                }
                for item in result.recommendations
            ],
            "persistence": {
                "run_id": str(run_id) if run_id else None,
                "saved": bool(run_id),
                "output_tables": ["ml02.ranking_runs", "ml02.ranking_results"] if run_id else [],
            },
        }
    except ViewerNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ViewerNotEligibleError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except psycopg.Error as exc:
        raise HTTPException(status_code=503, detail="Database query or output persistence failed") from exc


@app.get("/runs/{run_id}")
def get_run(run_id: UUID) -> dict[str, Any]:
    """Read back the stored ML-02 output rows for a previous run."""
    try:
        with get_connection() as conn:
            run = load_saved_run(conn, run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Ranking run not found")
        return run
    except psycopg.Error as exc:
        raise HTTPException(status_code=503, detail="Database query failed") from exc
