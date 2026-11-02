# ML-02 mock implementation: decisions and gaps

## Explicitly implemented

- Jaccard similarity over deduplicated active interest IDs.
- Current viewer intent and candidate intent read from visible active intent rows.
- Explicit compatibility scores from a demo-only mapping table.
- Profile completeness percentage converted to a 0–1 feature.
- Optional freshness from a demo-only timestamp table.
- Weighted score 45/25/15/15 and redundancy coefficient 0.10.
- Weight renormalization over available optional features.
- Complete cold-start mode returns an empty scored result with `COLD_START_NEEDS_INPUT`; no candidates, relevance scores or reasons are manufactured.
- Output contract includes rank position, clamped composite score, four feature sub-scores, signed diversity adjustment, model/rule SHA-256 hash and 1–3 factual reason codes.
- Candidates without at least one verified factual reason code are excluded from the explainable recommendation output.
- Factual interest and intent reason codes.
- SHA-256 tie-breaker using viewer, candidate and UTC date.
- Candidate safety exclusions in the mock ML-01 SQL query.
- Result persistence in local demo output tables.

## Not implemented / needs approval

| Item | Why not assumed | Required owner / next action |
|---|---|---|
| Production ML-01 integration | Ranking must consume the real eligible pool; mock SQL only simulates it | ML-01 + backend: approve request/response contract |
| Intent compatibility matrix | Workbook has intent codes but no final compatibility mapping | Product: approve compatible pairs, scores, reason codes and versioning |
| Activity timestamp and decay | No approved `last_active_at` field/source in the SQL schema | Database + Product: define source, freshness decay and consent |
| Redundancy penalty | Formula coefficient exists, but exact penalty input/algorithm is not finalized | ML + Product: define bounded input and diversity policy |
| Candidate mode | `analytics.discovery_impressions.mode` records impression mode; it is not proof of a candidate's selected mode | Product + DB: define candidate/viewer mode source and compatibility contract |
| Consent enforcement | Consent types/purposes are not fully specified in this module contract | Privacy + Product: identify exact required consent types and enforcement point |
| Exposure-aware tie-break | Workbook currently specifies deterministic SHA-256 tie-break; impressions use pseudonymous IDs | Keep hash tie-break for MVP; any exposure policy needs a privacy-safe design approval |
| Production output storage | Local `ml02.*` output tables retain operational IDs for demonstration | Security + DB: approve retention, access and deletion policy |

## Mock ML-01 exclusions used

A candidate is excluded before ranking if they are the viewer, account is not active, contact is unverified, age eligibility is not `eligible`, profile is missing/deleted/not visible, an active block exists in either direction, an active connection exists, a pending request has not expired, a request cooldown is active, or an unexpired dismissal matches `all` or the requested mode.

These query predicates are a demo subset and must be reconciled with ML-01's approved policy routines before production.
