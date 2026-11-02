-- Deterministic development fixtures. IDs are synthetic UUIDs, not real people.

INSERT INTO core.users (id, status, contact_verification_status, age_eligibility_status) VALUES
('00000000-0000-0000-0000-000000000101','active','verified','eligible'), -- viewer: complete profile
('00000000-0000-0000-0000-000000000102','active','verified','eligible'), -- viewer: complete cold start
('00000000-0000-0000-0000-000000000201','active','verified','eligible'),
('00000000-0000-0000-0000-000000000202','active','verified','eligible'),
('00000000-0000-0000-0000-000000000203','active','verified','eligible'),
('00000000-0000-0000-0000-000000000204','active','verified','eligible'),
('00000000-0000-0000-0000-000000000205','active','verified','eligible'),
('00000000-0000-0000-0000-000000000206','active','verified','eligible'),
('00000000-0000-0000-0000-000000000207','active','verified','eligible'),
('00000000-0000-0000-0000-000000000208','active','verified','eligible'),
('00000000-0000-0000-0000-000000000209','active','verified','eligible'),
('00000000-0000-0000-0000-000000000210','active','verified','eligible'),
('00000000-0000-0000-0000-000000000211','suspended','verified','eligible'),
('00000000-0000-0000-0000-000000000212','active','verified','eligible');

INSERT INTO core.profiles (user_id, display_name, bio, visibility_status, profile_completeness) VALUES
('00000000-0000-0000-0000-000000000101','Viewer Complete','Interested in building software projects.','visible',90),
('00000000-0000-0000-0000-000000000102','Viewer Cold Start',NULL,'visible',0),
('00000000-0000-0000-0000-000000000201','Candidate Atlas','AI and software engineering projects.','visible',90),
('00000000-0000-0000-0000-000000000202','Candidate Birch','Building web applications.','visible',80),
('00000000-0000-0000-0000-000000000203','Candidate Cedar','Learning AI and music production.','visible',65),
('00000000-0000-0000-0000-000000000204','Candidate Delta','Interested in meeting collaborators.','visible',95),
('00000000-0000-0000-0000-000000000205','Candidate Ember',NULL,'visible',20),
('00000000-0000-0000-0000-000000000206','Candidate Frost','Blocked fixture.','visible',85),
('00000000-0000-0000-0000-000000000207','Candidate Hidden','This profile should not be returned.','hidden',90),
('00000000-0000-0000-0000-000000000208','Candidate Connected','Already connected fixture.','visible',90),
('00000000-0000-0000-0000-000000000209','Candidate Pending','Pending request fixture.','visible',75),
('00000000-0000-0000-0000-000000000210','Candidate Dismissed','Dismissed fixture.','visible',70),
('00000000-0000-0000-0000-000000000211','Candidate Suspended','Suspended account fixture.','visible',100),
('00000000-0000-0000-0000-000000000212','Candidate Atlas Twin','Same feature values as Candidate Atlas.','visible',90);

INSERT INTO core.interests (id, slug, label, status) VALUES
('10000000-0000-0000-0000-000000000001','artificial-intelligence','Artificial Intelligence','active'),
('10000000-0000-0000-0000-000000000002','python','Python','active'),
('10000000-0000-0000-0000-000000000003','dbms','DBMS','active'),
('10000000-0000-0000-0000-000000000004','web-development','Web Development','active'),
('10000000-0000-0000-0000-000000000005','music','Music','active'),
('10000000-0000-0000-0000-000000000006','photography','Photography','active'),
('10000000-0000-0000-0000-000000000007','legacy-ml','Legacy ML Topic','deprecated');

-- Viewer 101 has three interests. Viewer 102 intentionally has none (complete cold-start case).
INSERT INTO core.user_interests (user_id, interest_id) VALUES
('00000000-0000-0000-0000-000000000101','10000000-0000-0000-0000-000000000001'),
('00000000-0000-0000-0000-000000000101','10000000-0000-0000-0000-000000000002'),
('00000000-0000-0000-0000-000000000101','10000000-0000-0000-0000-000000000003'),
('00000000-0000-0000-0000-000000000201','10000000-0000-0000-0000-000000000001'),
('00000000-0000-0000-0000-000000000201','10000000-0000-0000-0000-000000000002'),
('00000000-0000-0000-0000-000000000201','10000000-0000-0000-0000-000000000003'),
('00000000-0000-0000-0000-000000000202','10000000-0000-0000-0000-000000000001'),
('00000000-0000-0000-0000-000000000202','10000000-0000-0000-0000-000000000002'),
('00000000-0000-0000-0000-000000000202','10000000-0000-0000-0000-000000000004'),
('00000000-0000-0000-0000-000000000203','10000000-0000-0000-0000-000000000001'),
('00000000-0000-0000-0000-000000000203','10000000-0000-0000-0000-000000000005'),
('00000000-0000-0000-0000-000000000204','10000000-0000-0000-0000-000000000005'),
('00000000-0000-0000-0000-000000000204','10000000-0000-0000-0000-000000000006'),
('00000000-0000-0000-0000-000000000206','10000000-0000-0000-0000-000000000001'),
('00000000-0000-0000-0000-000000000208','10000000-0000-0000-0000-000000000002'),
('00000000-0000-0000-0000-000000000209','10000000-0000-0000-0000-000000000003'),
('00000000-0000-0000-0000-000000000210','10000000-0000-0000-0000-000000000001'),
('00000000-0000-0000-0000-000000000212','10000000-0000-0000-0000-000000000001'),
('00000000-0000-0000-0000-000000000212','10000000-0000-0000-0000-000000000002'),
('00000000-0000-0000-0000-000000000212','10000000-0000-0000-0000-000000000003');

INSERT INTO core.connection_intents (user_id, intent_code, status, visibility) VALUES
('00000000-0000-0000-0000-000000000101','collaboration','active','visible'),
('00000000-0000-0000-0000-000000000201','collaboration','active','visible'),
('00000000-0000-0000-0000-000000000202','collaboration','active','visible'),
('00000000-0000-0000-0000-000000000203','collaboration','active','visible'),
('00000000-0000-0000-0000-000000000204','networking','active','visible'),
('00000000-0000-0000-0000-000000000206','collaboration','active','visible'),
('00000000-0000-0000-0000-000000000208','collaboration','active','visible'),
('00000000-0000-0000-0000-000000000209','collaboration','active','visible'),
('00000000-0000-0000-0000-000000000210','collaboration','active','visible'),
('00000000-0000-0000-0000-000000000212','collaboration','active','visible');

-- MOCK-ONLY example mapping. Product must supply and approve real compatibility rules.
INSERT INTO core.mock_intent_compatibility
(viewer_intent_code, candidate_intent_code, compatibility_score, reason_code, enabled) VALUES
('collaboration','collaboration',1.0,'INTENT_MATCH_COLLABORATION',TRUE),
('collaboration','networking',0.5,'INTENT_COMPATIBLE_NETWORKING',TRUE);

-- Negative eligibility / relationship fixtures for viewer 101.
INSERT INTO core.blocks (blocker_user_id, blocked_user_id, reason_code)
VALUES ('00000000-0000-0000-0000-000000000101','00000000-0000-0000-0000-000000000206','mock_test_block');

INSERT INTO core.connections (user_low_id, user_high_id, status)
VALUES ('00000000-0000-0000-0000-000000000101','00000000-0000-0000-0000-000000000208','active');

INSERT INTO core.connection_requests
(sender_user_id, recipient_user_id, status, created_at, expires_at)
VALUES ('00000000-0000-0000-0000-000000000101','00000000-0000-0000-0000-000000000209',
        'pending', now() - interval '1 hour', now() + interval '6 days');

INSERT INTO core.discovery_dismissals
(viewer_user_id, candidate_user_id, scope, created_at, expires_at)
VALUES ('00000000-0000-0000-0000-000000000101','00000000-0000-0000-0000-000000000210',
        'all', now() - interval '1 day', now() + interval '29 days');

-- DEV-ONLY freshness fixtures; exact timestamps intentionally match for 201 and 212 (tie demonstration).
INSERT INTO core.mock_activity (user_id, last_active_at) VALUES
('00000000-0000-0000-0000-000000000201', now() - interval '1 day'),
('00000000-0000-0000-0000-000000000202', now() - interval '2 days'),
('00000000-0000-0000-0000-000000000203', now() - interval '5 days'),
('00000000-0000-0000-0000-000000000204', now() - interval '12 hours'),
('00000000-0000-0000-0000-000000000205', now() - interval '30 days'),
('00000000-0000-0000-0000-000000000206', now() - interval '1 day'),
('00000000-0000-0000-0000-000000000208', now() - interval '1 day'),
('00000000-0000-0000-0000-000000000209', now() - interval '1 day'),
('00000000-0000-0000-0000-000000000210', now() - interval '1 day'),
('00000000-0000-0000-0000-000000000212', now() - interval '1 day');

-- Candidate 205 intentionally has no interests, no intent and no activity.
-- Candidate 207 is hidden; 211 is suspended. These should never enter ML-02.
