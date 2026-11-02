# ML-02 Working Model — Mock PostgreSQL → MALS-Rank → Output

This is a runnable **development prototype** for ML-02, using the agreed stack:

- Python 3.10+
- FastAPI
- PostgreSQL 16
- psycopg 3
- Pytest

It creates mock SQL input tables, inserts synthetic records, extracts the viewer and candidate features, runs the ML-02 ranking logic, returns ranked output, and saves each run to separate output tables.

> **Important:** All records in this project are synthetic. `sql/001_mock_schema.sql` is a development fixture, not a production migration. The workbook marks parts of the source DDL and product rules as draft or decision-gated. Do not apply this SQL to a production database.

## 1. Run with Docker Desktop (recommended)

Install/start Docker Desktop, open PowerShell in this project folder, and run:

```powershell
docker compose up --build
```

The first startup creates PostgreSQL, applies the mock schema and seed data, then starts FastAPI.

Open:

- Swagger UI: http://localhost:8000/docs
- Health: http://localhost:8000/health
- Mock scenarios: http://localhost:8000/mock/scenarios

PostgreSQL is exposed on `localhost:5433` to avoid colliding with a local PostgreSQL server on port 5432.

To stop:

```powershell
docker compose down
```

To reset the mock database and rerun the SQL seed scripts (also required after switching from an earlier prototype schema):

```powershell
docker compose down -v
docker compose up --build
```

`-v` deletes the demo database volume. Use it only when you want to reset demo data.

## 2. Run without Docker

You need a local PostgreSQL 16+ database. Create a database/user, then run the SQL files in order:

```powershell
psql -U postgres -d ml02_demo -f .\sql\001_mock_schema.sql
psql -U postgres -d ml02_demo -f .\sql\002_mock_seed.sql
```

Create and activate a Python environment:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[test]"
```

Set the connection string for a local database (adjust credentials/port):

```powershell
$env:DATABASE_URL = "postgresql://ml02_user:your_password@localhost:5432/ml02_demo"
$env:ML02_ENABLE_MOCK_FRESHNESS = "true"
$env:ML02_FRESHNESS_HALF_LIFE_DAYS = "7"
```

Run tests and API:

```powershell
pytest -q
uvicorn app.main:app --reload
```

## 3. What the mock database contains

| Schema/table | How ML-02 uses it | Source status |
|---|---|---|
| `core.users` | Account state, verification and age-eligibility state | Source-workbook table; mock subset of columns |
| `core.profiles` | Visibility and profile completeness | Source-workbook table; mock subset of columns |
| `core.interests` | Active interest taxonomy and display labels | Source-workbook table |
| `core.user_interests` | Viewer/candidate interest IDs | Source-workbook table |
| `core.connection_intents` | Current visible intent | Source-workbook table |
| `core.blocks` | Exclude blocked pairs in either direction | Source-workbook table |
| `core.connections` | Exclude active existing connections | Source-workbook table |
| `core.connection_requests` | Exclude pending requests / active cooldowns | Source-workbook table |
| `core.discovery_dismissals` | Exclude active dismissals | Source-workbook table |
| `core.user_consents` | Mocked consent history table; policy-specific gates not invented | Source-workbook table |
| `core.mock_intent_compatibility` | Supplies explicit 0–1 intent compatibility in the demo | **DEV-ONLY extra table**; product must approve real mapping |
| `core.mock_activity` | Provides `last_active_at` for the freshness demo | **DEV-ONLY extra table**; workbook has no trusted activity timestamp field |
| `ml02.ranking_runs` | Stores one execution/run summary | **DEV-ONLY output table** |
| `ml02.ranking_results` | Stores ordered candidate IDs, score, components and reason codes | **DEV-ONLY output table** |
| `analytics.discovery_impressions` | Schema fixture showing the expected shape of display logging | Source-workbook table; API does not write impressions automatically |
| `analytics.product_events` | Schema fixture for future outcome evaluation | Source-workbook table; empty until event taxonomy/outcome contract is approved |

The mock SQL query simulates ML-01's pre-filtered eligible candidate pool. It is not a replacement for the actual ML-01 service or its policy routines.

## 4. Demo viewers and scenarios

Use these synthetic UUIDs in Swagger:

| Viewer | UUID | Scenario |
|---|---|---|
| Complete viewer | `00000000-0000-0000-0000-000000000101` | Interests: AI, Python, DBMS; intent: collaboration |
| Cold-start viewer | `00000000-0000-0000-0000-000000000102` | No interests, no intent, no history |

Candidate fixtures returned for viewer 101:

| Candidate UUID suffix | Scenario |
|---|---|
| `201` | Three shared interests; strong candidate |
| `202` | Two shared interests |
| `203` | One shared interest |
| `204` | No shared interests; explicit mock intent compatibility |
| `205` | No interests, no intent and no activity; partial profile |
| `212` | Same feature values as candidate 201; exact-score tie test |

Excluded fixtures for viewer 101:

- `206`: blocked
- `207`: hidden profile
- `208`: already connected
- `209`: pending connection request
- `210`: dismissed
- `211`: suspended account

## 5. API workflow — input → ranking → output

### A. View the exact extracted input

```http
GET /debug/input/00000000-0000-0000-0000-000000000101
```

This returns the input feature values extracted from PostgreSQL **before** scoring: viewer interests/intent, candidate IDs, candidate interests, intent score, profile completeness and freshness.

### B. Run ML-02 and save the output

```http
POST /rank/00000000-0000-0000-0000-000000000101
```

Example response shape:

```json
{
  "viewer_id": "00000000-0000-0000-0000-000000000101",
  "result_status": "OK",
  "ranking_mode": "PERSONALIZED",
  "model_version": "ml02-mals-rank-v0.3.0",
  "model_rule_version_hash": "d226a1be618f7ad779e2957f76d5f5ba10bcfcb1ac64744a18bc8e14d6ec3eb2",
  "recommendations": [
    {
      "candidate_id": "00000000-0000-0000-0000-000000000201",
      "rank_position": 1,
      "composite_relevance_score": 0.970855,
      "feature_sub_scores": {
        "interest": 1.0,
        "intent": 1.0,
        "profile": 0.9,
        "freshness": 0.9057
      },
      "diversity_adjustment": 0.0,
      "reason_codes": [
        "SHARED_INTEREST_ARTIFICIAL_INTELLIGENCE",
        "SHARED_INTEREST_DBMS",
        "SHARED_INTEREST_PYTHON"
      ]
    }
  ],
  "persistence": {
    "run_id": "<generated-run-uuid>",
    "saved": true,
    "output_tables": ["ml02.ranking_runs", "ml02.ranking_results"]
  }
}
```

Contract rules:

- `rank_position` is sequential, starting at 1.
- `composite_relevance_score` is always a numeric value clamped to `[0.0, 1.0]` for returned recommendations.
- `feature_sub_scores` contains the interest, intent, profile and freshness component scores. Unavailable optional features are `null` and their weights are renormalized.
- `diversity_adjustment` is a signed additive score delta: `0.0` means no adjustment; negative values reduce the composite score.
- `model_rule_version_hash` is a SHA-256 hash of the model version, weights, scoring policy, reason-code policy and tie-break policy.
- Each returned candidate has 1–3 deterministic reason codes derived from shared active interest taxonomy facts or an approved compatibility mapping between active, visible intents. Interest reason-code generation assumes the queried active interest records are discoverable; apply any production per-interest visibility/consent rule before building these facts.
- Candidates without at least one factual reason code are not returned. No explanation is fabricated.
- Ineligible candidates are removed before ranking. If no eligible candidates remain, `recommendations` is `[]` and `result_status` is `NO_ELIGIBLE_CANDIDATES`.

When no candidate passes ML-01, the response has `result_status = NO_ELIGIBLE_CANDIDATES` and an empty `recommendations` array. When eligible candidates exist but none has a factual explainability reason, the response has `result_status = NO_EXPLAINABLE_MATCHES` and an empty array.

To calculate without saving:

```http
POST /rank/00000000-0000-0000-0000-000000000101?persist=false
```

### C. Test full cold start

```http
GET  /debug/input/00000000-0000-0000-0000-000000000102
POST /rank/00000000-0000-0000-0000-000000000102
```

Expected: `result_status = COLD_START_NEEDS_INPUT`, `ranking_mode = COLD_START`, and `recommendations = []`. ML-02 does not invent a relevance score or reasons when the viewer has no interests or intent. Generic Explore ordering, if required by Product, should be a separate unscored discovery fallback outside this ML-02 ranked-output contract.

### D. Read a saved output

Copy the `run_id` returned by `/rank/...` and call:

```http
GET /runs/{run_id}
```

## 6. Scoring design

Default workbook formula:

```text
score = 0.45 * interest
      + 0.25 * intent
      + 0.15 * profile
      + 0.15 * freshness
      + diversity_adjustment

where diversity_adjustment = -0.10 * redundancy_penalty
```

- Interest: Jaccard similarity over unique active interest IDs.
- Intent: score read from the explicitly seeded mock compatibility table. This is not a product-approved production mapping.
- Profile: `profile_completeness` percentage divided by 100.
- Freshness: exponential half-life transform from the development-only activity table, with a 7-day demo half-life.
- Redundancy: fixed to zero because the product diversity formula/input has not been approved.
- Missing optional features: available feature weights are renormalized.
- Complete viewer cold start: no meaningful viewer interest/intent signal, therefore ML-02 returns an empty ranked result with `COLD_START_NEEDS_INPUT`; it does not fabricate candidate scores or reasons.
- Candidates with no 1–3 factual reason codes are excluded from the explainable ranked output, even if profile/freshness fields alone could produce a numeric score.
- Tie-break: SHA-256 over `(viewer_id, candidate_id, UTC date)`, as specified in the ML-02 workbook. It changes display order only; it does not change relevance score.

## 7. Important production gaps (do not hide these)

1. Replace the mock ML-01 candidate SQL with the approved ML-01 API/interface.
2. Replace `core.mock_intent_compatibility` with Product-approved compatibility rules and a versioned contract.
3. Replace `core.mock_activity` only after the Database team provides an approved activity timestamp and Product approves the freshness decay policy. `profiles.updated_at` is not a substitute for user activity.
4. Keep redundancy penalty at zero until the diversity policy and input source are agreed.
5. `analytics.discovery_impressions` uses pseudonymous IDs. Do not join those directly to operational user IDs. The API intentionally does not write an impression merely because it returned a candidate; only confirmed UI displays should be logged.
6. Mode-specific candidate eligibility, consent type enforcement and user-selected mode require approved product/SQL contracts. The `mode` query parameter in this prototype is only used for dismissal scope and run metadata.
7. The `ml02.*` tables store operational IDs for this local demo. Production persistence, access control, pseudonymization, deletion and retention need privacy/security review.
8. The workbook has differing latency targets in different sections. Agree one P95 SLO and benchmark it on representative infrastructure before sign-off.

## 8. Code map

| Path | Purpose |
|---|---|
| `sql/001_mock_schema.sql` | Creates mock input tables and ML-02 output tables |
| `sql/002_mock_seed.sql` | Inserts all synthetic demo rows |
| `sql/003_inspect_demo.sql` | Handy SQL queries to inspect input, candidate pool and saved output |
| `app/repository.py` | Reads PostgreSQL inputs, applies mock ML-01 filters, maps rows to model features, saves outputs |
| `app/main.py` | FastAPI endpoints |
| `src/ml02/features.py` | Jaccard, completeness and freshness feature calculations |
| `src/ml02/scoring.py` | Weighted scoring and missing-feature renormalization |
| `src/ml02/ranker.py` | Ranking, cold start, reason codes and deterministic tie-break |
| `src/ml02/models.py` | Typed input/output structures |
| `tests/` | Automated unit tests |

## 9. Test

```powershell
pytest -q
```

The test suite validates the pure ML-02 engine. Database integration should additionally be demonstrated through the FastAPI endpoints after `docker compose up --build`.
