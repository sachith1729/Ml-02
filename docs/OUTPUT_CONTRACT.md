# ML-02 output contract

The `POST /rank/{viewer_id}` endpoint returns the contract below. `GET /runs/{run_id}` returns the same recommendation fields from persisted rows, plus run metadata.

## Successful personalized run

```json
{
  "viewer_id": "<viewer-uuid>",
  "result_status": "OK",
  "ranking_mode": "PERSONALIZED",
  "model_version": "ml02-mals-rank-v0.3.0",
  "model_rule_version_hash": "<sha256-hex-64>",
  "recommendations": [
    {
      "candidate_id": "<candidate-uuid>",
      "rank_position": 1,
      "composite_relevance_score": 0.923456,
      "feature_sub_scores": {
        "interest": 0.75,
        "intent": 1.0,
        "profile": 0.9,
        "freshness": null
      },
      "diversity_adjustment": 0.0,
      "reason_codes": [
        "SHARED_INTEREST_DISTRIBUTED_SYSTEMS",
        "INTENT_MATCH_COLLABORATION"
      ]
    }
  ],
  "persistence": {
    "run_id": "<run-uuid-or-null>",
    "saved": true,
    "output_tables": ["ml02.ranking_runs", "ml02.ranking_results"]
  }
}
```

## Empty results

No eligible candidate: `result_status = NO_ELIGIBLE_CANDIDATES`, `ranking_mode = EMPTY`, `recommendations = []`.

Complete viewer cold start: `result_status = COLD_START_NEEDS_INPUT`, `ranking_mode = COLD_START`, `recommendations = []`. Generic Explore may be implemented separately, but must not be represented as personalized ML-02 recommendations.

Eligible candidates but no scoreable, factual reason: `result_status = NO_EXPLAINABLE_MATCHES`, `ranking_mode = EMPTY`, `recommendations = []`. This avoids returning a relevance score without a truthful explanation.

## Field rules

- `candidate_id`: ID supplied by the ML-01 candidate pool; ML-02 never creates candidates.
- `rank_position`: 1-based position after descending composite score and deterministic tie-breaking.
- `composite_relevance_score`: numeric and clamped to `[0.0, 1.0]`.
- `feature_sub_scores`: normalized feature values in `[0.0, 1.0]`; `null` means unavailable. Missing optional feature weights are renormalized.
- `diversity_adjustment`: signed additive score delta in `[-0.10, 0.0]` under the current default configuration. Zero means no diversity adjustment is active.
- `model_rule_version_hash`: SHA-256 of model version, scoring/rule versions, weights, transforms and active runtime rule configuration.
- `reason_codes`: 1–3 deterministic codes grounded in shared active interests or an approved compatibility mapping between active, visible intents. Candidates without at least one supported reason are excluded.
- If no eligible candidates remain, return an empty array. Never manufacture candidates or reasons.

## Current implementation decisions

- Cold-start users receive an empty ML-02 ranked result until they provide an interest or intent signal. Any unscored generic Explore feed belongs to a separate product fallback.
- Candidate scores are calculated only for candidates with at least one valid reason code.
- Interest reason codes use active taxonomy slugs. The mock schema does not define a per-interest visibility column; the repository therefore assumes active interest records selected for this endpoint are discoverable. If production has per-interest visibility/consent controls, the SQL repository must enforce them before returning reason facts.
