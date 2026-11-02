-- ML-02 DEVELOPMENT MOCK DATABASE ONLY.
-- Names and the source-aligned fields follow the uploaded workbook where possible.
-- This is NOT a production migration. The workbook marks several DDL decisions as draft/gated.

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS analytics;
CREATE SCHEMA IF NOT EXISTS ml02;

CREATE TABLE core.users (
    id UUID PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','suspended','deactivated','deletion_pending')),
    timezone TEXT NOT NULL DEFAULT 'UTC',
    contact_verification_status TEXT NOT NULL DEFAULT 'unverified'
        CHECK (contact_verification_status IN ('unverified','pending','verified','failed')),
    age_eligibility_status TEXT NOT NULL DEFAULT 'unknown'
        CHECK (age_eligibility_status IN ('unknown','eligible','ineligible','review_required')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ NULL
);

CREATE TABLE core.profiles (
    user_id UUID PRIMARY KEY REFERENCES core.users(id) ON DELETE RESTRICT,
    display_name TEXT NOT NULL CHECK (length(trim(display_name)) BETWEEN 1 AND 80),
    bio TEXT NULL CHECK (bio IS NULL OR length(bio) <= 1000),
    visibility_status TEXT NOT NULL DEFAULT 'hidden'
        CHECK (visibility_status IN ('visible','hidden','under_review')),
    profile_completeness SMALLINT NOT NULL DEFAULT 0
        CHECK (profile_completeness BETWEEN 0 AND 100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ NULL
);

CREATE TABLE core.interests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug TEXT NOT NULL UNIQUE,
    label TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','deprecated')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE core.user_interests (
    user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    interest_id UUID NOT NULL REFERENCES core.interests(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, interest_id)
);

CREATE TABLE core.connection_intents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    intent_code TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','inactive')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    visibility TEXT NOT NULL DEFAULT 'hidden' CHECK (visibility IN ('visible','hidden'))
);
CREATE INDEX ix_mock_connection_intents_user_active
    ON core.connection_intents(user_id, updated_at DESC)
    WHERE status = 'active' AND visibility = 'visible';

CREATE TABLE core.blocks (
    blocker_user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    blocked_user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    reason_code TEXT NULL,
    removed_at TIMESTAMPTZ NULL,
    PRIMARY KEY (blocker_user_id, blocked_user_id),
    CHECK (blocker_user_id <> blocked_user_id),
    CHECK (removed_at IS NULL OR removed_at >= created_at)
);

CREATE TABLE core.connections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_low_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    user_high_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active','disconnected','blocked','closed')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (user_low_id < user_high_id)
);

CREATE TABLE core.connection_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sender_user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    recipient_user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending','accepted','declined','withdrawn','cancelled','expired')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    responded_at TIMESTAMPTZ NULL,
    cooldown_until TIMESTAMPTZ NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    CHECK (sender_user_id <> recipient_user_id),
    CHECK (responded_at IS NULL OR responded_at >= created_at),
    CHECK (cooldown_until IS NULL OR cooldown_until >= created_at),
    CHECK (expires_at > created_at)
);

CREATE TABLE core.discovery_dismissals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    viewer_user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    candidate_user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    scope TEXT NOT NULL DEFAULT 'all',
    reason_code TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ NULL,
    CHECK (viewer_user_id <> candidate_user_id),
    CHECK (expires_at IS NULL OR expires_at > created_at)
);

CREATE TABLE core.user_consents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    consent_type TEXT NOT NULL,
    policy_version TEXT NOT NULL,
    decision TEXT NOT NULL CHECK (decision IN ('granted','withdrawn','declined')),
    captured_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    source TEXT NOT NULL,
    metadata JSONB NULL
);

-- DEVELOPMENT-ONLY EXTENSION: the workbook requires an approved intent-compatibility contract,
-- but does not define this table. Seeded mapping values are mock values, not product policy.
CREATE TABLE core.mock_intent_compatibility (
    viewer_intent_code TEXT NOT NULL,
    candidate_intent_code TEXT NOT NULL,
    compatibility_score NUMERIC(5,4) NOT NULL CHECK (compatibility_score BETWEEN 0 AND 1),
    reason_code TEXT NULL,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    PRIMARY KEY (viewer_intent_code, candidate_intent_code)
);

-- DEVELOPMENT-ONLY EXTENSION: the workbook does not define a trusted last_active_at column.
-- This table exists only to exercise the freshness feature in the demo.
CREATE TABLE core.mock_activity (
    user_id UUID PRIMARY KEY REFERENCES core.users(id) ON DELETE RESTRICT,
    last_active_at TIMESTAMPTZ NOT NULL
);

-- Source-aligned shape from the workbook. In this mock it records no real display event automatically;
-- only a frontend-confirmed display should create an impression in a production flow.
CREATE TABLE analytics.discovery_impressions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id UUID NOT NULL,
    viewer_pseudonym_id UUID NOT NULL,
    candidate_pseudonym_id UUID NOT NULL,
    position SMALLINT NOT NULL CHECK (position >= 0),
    reason_codes TEXT[] NOT NULL DEFAULT '{}',
    mode TEXT NOT NULL DEFAULT 'default',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Source-workbook product event shape. No event rows are seeded because the event catalogue,
-- outcome definitions and allowed properties must be approved before meaningful evaluation.
CREATE TABLE analytics.product_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type TEXT NOT NULL,
    actor_pseudonym_id UUID NULL,
    aggregate_type TEXT NULL,
    event_time TIMESTAMPTZ NOT NULL DEFAULT now(),
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    properties JSONB NOT NULL DEFAULT '{}'::jsonb,
    source_outbox_event_id UUID NULL UNIQUE
);

-- ML-02 prototype output/audit tables. These are demo persistence tables, not approved production DDL.
CREATE TABLE ml02.ranking_runs (
    run_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    viewer_user_id UUID NOT NULL,
    result_status TEXT NOT NULL CHECK (result_status IN ('OK','NO_ELIGIBLE_CANDIDATES','COLD_START_NEEDS_INPUT','NO_EXPLAINABLE_MATCHES')),
    ranking_mode TEXT NOT NULL CHECK (ranking_mode IN ('PERSONALIZED','COLD_START','EMPTY')),
    personalized BOOLEAN NOT NULL,
    model_version TEXT NOT NULL,
    model_rule_version_hash CHAR(64) NOT NULL,
    request_mode TEXT NOT NULL DEFAULT 'default',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE ml02.ranking_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL REFERENCES ml02.ranking_runs(run_id) ON DELETE CASCADE,
    candidate_user_id UUID NOT NULL,
    rank_position INTEGER NOT NULL CHECK (rank_position >= 1),
    relevance_score NUMERIC(8,6) NOT NULL CHECK (relevance_score BETWEEN 0 AND 1),
    feature_scores JSONB NOT NULL,
    reason_codes TEXT[] NOT NULL CHECK (cardinality(reason_codes) BETWEEN 1 AND 3),
    tie_break_hash TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (run_id, candidate_user_id),
    UNIQUE (run_id, rank_position)
);

CREATE INDEX ix_mock_user_interests_interest ON core.user_interests(interest_id, user_id);
CREATE INDEX ix_mock_dismissals_lookup ON core.discovery_dismissals(viewer_user_id, candidate_user_id, expires_at);
CREATE INDEX ix_mock_connections_pair ON core.connections(user_low_id, user_high_id, status);
