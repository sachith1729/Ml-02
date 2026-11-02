-- Run these queries in the ml02_demo database to inspect the mock input and output.

-- 1) Viewer 101 interests and labels.
SELECT ui.user_id, i.id AS interest_id, i.slug, i.label
FROM core.user_interests ui
JOIN core.interests i ON i.id = ui.interest_id
WHERE ui.user_id = '00000000-0000-0000-0000-000000000101'
  AND i.status = 'active'
ORDER BY i.label;

-- 2) Current visible intents for the demo viewer and candidates.
SELECT user_id, intent_code, status, visibility, updated_at
FROM core.connection_intents
WHERE status = 'active' AND visibility = 'visible'
ORDER BY user_id;

-- 3) Mock ML-01 candidate pool for viewer 101 (exclusions are implemented in app/repository.py).
SELECT u.id AS candidate_id, p.display_name, p.profile_completeness, p.visibility_status
FROM core.users u
JOIN core.profiles p ON p.user_id = u.id
WHERE u.status = 'active'
  AND u.contact_verification_status = 'verified'
  AND u.age_eligibility_status = 'eligible'
  AND p.visibility_status = 'visible'
ORDER BY p.display_name;

-- 4) Inspect the latest persisted model run.
SELECT * FROM ml02.ranking_runs ORDER BY created_at DESC LIMIT 5;

-- 5) Inspect ranked outputs for the latest run.
SELECT rr.run_id, rr.rank_position, rr.candidate_user_id,
       rr.relevance_score, rr.feature_scores, rr.reason_codes
FROM ml02.ranking_results rr
JOIN ml02.ranking_runs r ON r.run_id = rr.run_id
ORDER BY r.created_at DESC, rr.rank_position;

-- 6) Confirm that only real UI displays are logged as impressions.
-- This demo does not automatically write impressions when it returns recommendations.
SELECT * FROM analytics.discovery_impressions ORDER BY created_at DESC LIMIT 20;
