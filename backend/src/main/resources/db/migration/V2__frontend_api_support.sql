ALTER TABLE auth_accounts ADD COLUMN IF NOT EXISTS provider_email VARCHAR(255) NULL;

UPDATE auth_accounts
SET provider_email = provider_user_id
WHERE provider = 'LOCAL' AND provider_email IS NULL;

ALTER TABLE experiences
    ADD CONSTRAINT uk_experiences_candidate UNIQUE (candidate_id);

CREATE INDEX idx_project_files_user_created ON project_files(user_id, created_at DESC);
CREATE INDEX idx_experience_candidates_run_created ON experience_candidates(analysis_run_id, created_at);
CREATE INDEX idx_gap_questions_experience_order ON gap_questions(experience_id, display_order);
