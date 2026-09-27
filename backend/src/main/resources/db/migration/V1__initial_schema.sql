CREATE TABLE users (
    id UUID PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'ACTIVE',
    onboarding_completed_at TIMESTAMP NULL,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    deleted_at TIMESTAMP NULL,
    CONSTRAINT ck_users_status CHECK (status IN ('ACTIVE', 'WITHDRAWN'))
);

CREATE TABLE auth_accounts (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    provider VARCHAR(30) NOT NULL,
    provider_user_id VARCHAR(255) NOT NULL,
    provider_email VARCHAR(255) NULL,
    password_hash VARCHAR(255) NULL,
    created_at TIMESTAMP NOT NULL,
    CONSTRAINT uk_auth_accounts_provider_user UNIQUE (provider, provider_user_id),
    CONSTRAINT ck_auth_accounts_provider CHECK (provider IN ('NAVER', 'KAKAO', 'LOCAL')),
    CONSTRAINT ck_auth_accounts_password CHECK (
        (provider = 'LOCAL' AND password_hash IS NOT NULL)
        OR (provider <> 'LOCAL' AND password_hash IS NULL)
    )
);

CREATE TABLE user_sessions (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    refresh_token_hash VARCHAR(255) NOT NULL UNIQUE,
    expires_at TIMESTAMP NOT NULL,
    revoked_at TIMESTAMP NULL,
    created_at TIMESTAMP NOT NULL
);

CREATE TABLE password_reset_tokens (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash VARCHAR(255) NOT NULL UNIQUE,
    expires_at TIMESTAMP NOT NULL,
    used_at TIMESTAMP NULL,
    created_at TIMESTAMP NOT NULL
);

CREATE TABLE projects (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id),
    name VARCHAR(200) NOT NULL,
    status VARCHAR(30) NOT NULL,
    activity_type VARCHAR(100) NULL,
    user_role VARCHAR(200) NULL,
    team_size INTEGER NULL,
    started_at DATE NULL,
    ended_at DATE NULL,
    description VARCHAR(200) NULL,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    deleted_at TIMESTAMP NULL,
    CONSTRAINT ck_projects_status CHECK (status IN ('IN_PROGRESS', 'COMPLETED')),
    CONSTRAINT ck_projects_dates CHECK (ended_at IS NULL OR started_at IS NULL OR ended_at >= started_at)
);

CREATE TABLE project_tags (
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    display_order INTEGER NOT NULL,
    tag VARCHAR(50) NOT NULL,
    PRIMARY KEY (project_id, display_order),
    CONSTRAINT uk_project_tags_value UNIQUE (project_id, tag)
);

CREATE TABLE quick_logs (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id),
    project_id UUID NULL REFERENCES projects(id) ON DELETE SET NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    deleted_at TIMESTAMP NULL
);

CREATE TABLE project_suggestions (
    id UUID PRIMARY KEY,
    quick_log_id UUID NOT NULL REFERENCES quick_logs(id) ON DELETE CASCADE,
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    confidence NUMERIC(5,4) NULL,
    status VARCHAR(30) NOT NULL,
    created_at TIMESTAMP NOT NULL,
    CONSTRAINT uk_project_suggestions_log_project UNIQUE (quick_log_id, project_id),
    CONSTRAINT ck_project_suggestions_confidence CHECK (confidence IS NULL OR confidence BETWEEN 0 AND 1)
);

CREATE TABLE project_files (
    id UUID PRIMARY KEY,
    project_id UUID NOT NULL REFERENCES projects(id),
    user_id UUID NOT NULL REFERENCES users(id),
    original_name VARCHAR(255) NOT NULL,
    storage_key VARCHAR(500) NOT NULL UNIQUE,
    mime_type VARCHAR(100) NOT NULL,
    size_bytes BIGINT NOT NULL,
    processing_status VARCHAR(30) NOT NULL,
    created_at TIMESTAMP NOT NULL,
    deleted_at TIMESTAMP NULL,
    CONSTRAINT ck_project_files_size CHECK (size_bytes >= 0)
);

CREATE TABLE analysis_runs (
    id UUID PRIMARY KEY,
    project_id UUID NOT NULL REFERENCES projects(id),
    run_type VARCHAR(30) NOT NULL,
    status VARCHAR(30) NOT NULL,
    model_version VARCHAR(100) NULL,
    started_at TIMESTAMP NULL,
    completed_at TIMESTAMP NULL,
    created_at TIMESTAMP NOT NULL,
    CONSTRAINT ck_analysis_runs_dates CHECK (
        completed_at IS NULL OR started_at IS NULL OR completed_at >= started_at
    )
);

CREATE TABLE analysis_input_files (
    analysis_run_id UUID NOT NULL REFERENCES analysis_runs(id) ON DELETE CASCADE,
    project_file_id UUID NOT NULL REFERENCES project_files(id),
    PRIMARY KEY (analysis_run_id, project_file_id)
);

CREATE TABLE analysis_input_logs (
    analysis_run_id UUID NOT NULL REFERENCES analysis_runs(id) ON DELETE CASCADE,
    quick_log_id UUID NOT NULL REFERENCES quick_logs(id),
    PRIMARY KEY (analysis_run_id, quick_log_id)
);

CREATE TABLE experience_candidates (
    id UUID PRIMARY KEY,
    analysis_run_id UUID NOT NULL REFERENCES analysis_runs(id) ON DELETE CASCADE,
    merged_into_id UUID NULL REFERENCES experience_candidates(id) ON DELETE SET NULL,
    title VARCHAR(255) NOT NULL,
    summary TEXT NULL,
    draft_content JSONB NULL,
    status VARCHAR(30) NOT NULL,
    created_at TIMESTAMP NOT NULL,
    CONSTRAINT ck_experience_candidates_not_self CHECK (merged_into_id IS NULL OR merged_into_id <> id)
);

CREATE TABLE experiences (
    id UUID PRIMARY KEY,
    project_id UUID NOT NULL REFERENCES projects(id),
    candidate_id UUID NULL REFERENCES experience_candidates(id) ON DELETE SET NULL,
    title VARCHAR(255) NOT NULL,
    summary TEXT NULL,
    context TEXT NULL,
    contribution TEXT NULL,
    decision_reason TEXT NULL,
    action TEXT NULL,
    result TEXT NULL,
    learning TEXT NULL,
    status VARCHAR(30) NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    deleted_at TIMESTAMP NULL,
    CONSTRAINT ck_experiences_version CHECK (version > 0)
);

CREATE TABLE evidence_items (
    id UUID PRIMARY KEY,
    project_id UUID NOT NULL REFERENCES projects(id),
    project_file_id UUID NULL REFERENCES project_files(id) ON DELETE SET NULL,
    quick_log_id UUID NULL REFERENCES quick_logs(id) ON DELETE SET NULL,
    excerpt TEXT NULL,
    location VARCHAR(255) NULL,
    created_at TIMESTAMP NOT NULL,
    CONSTRAINT ck_evidence_items_single_source CHECK (
        (CASE WHEN project_file_id IS NULL THEN 0 ELSE 1 END)
        + (CASE WHEN quick_log_id IS NULL THEN 0 ELSE 1 END) = 1
    )
);

CREATE TABLE experience_evidence (
    experience_id UUID NOT NULL REFERENCES experiences(id) ON DELETE CASCADE,
    evidence_item_id UUID NOT NULL REFERENCES evidence_items(id) ON DELETE CASCADE,
    section_type VARCHAR(30) NOT NULL,
    PRIMARY KEY (experience_id, evidence_item_id, section_type)
);

CREATE TABLE review_sessions (
    id UUID PRIMARY KEY,
    project_id UUID NOT NULL REFERENCES projects(id),
    analysis_run_id UUID NULL REFERENCES analysis_runs(id) ON DELETE SET NULL,
    status VARCHAR(30) NOT NULL,
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP NULL,
    CONSTRAINT ck_review_sessions_dates CHECK (completed_at IS NULL OR completed_at >= started_at)
);

CREATE TABLE review_items (
    id UUID PRIMARY KEY,
    review_session_id UUID NOT NULL REFERENCES review_sessions(id) ON DELETE CASCADE,
    experience_id UUID NULL REFERENCES experiences(id) ON DELETE SET NULL,
    candidate_id UUID NULL REFERENCES experience_candidates(id) ON DELETE SET NULL,
    item_type VARCHAR(40) NOT NULL,
    proposed_content TEXT NULL,
    confirmed_content TEXT NULL,
    decision VARCHAR(30) NOT NULL DEFAULT 'PENDING',
    display_order INTEGER NOT NULL,
    reviewed_at TIMESTAMP NULL,
    CONSTRAINT ck_review_items_target CHECK (
        (CASE WHEN experience_id IS NULL THEN 0 ELSE 1 END)
        + (CASE WHEN candidate_id IS NULL THEN 0 ELSE 1 END) = 1
    ),
    CONSTRAINT uk_review_items_order UNIQUE (review_session_id, display_order)
);

CREATE TABLE review_item_evidence (
    review_item_id UUID NOT NULL REFERENCES review_items(id) ON DELETE CASCADE,
    evidence_item_id UUID NOT NULL REFERENCES evidence_items(id) ON DELETE CASCADE,
    PRIMARY KEY (review_item_id, evidence_item_id)
);

CREATE TABLE gap_questions (
    id UUID PRIMARY KEY,
    review_item_id UUID NULL REFERENCES review_items(id) ON DELETE SET NULL,
    experience_id UUID NOT NULL REFERENCES experiences(id) ON DELETE CASCADE,
    target_section VARCHAR(30) NOT NULL,
    question TEXT NOT NULL,
    suggested_answers JSONB NULL,
    display_order INTEGER NOT NULL,
    created_at TIMESTAMP NOT NULL,
    CONSTRAINT uk_gap_questions_order UNIQUE (experience_id, display_order)
);

CREATE TABLE gap_answers (
    id UUID PRIMARY KEY,
    question_id UUID NOT NULL REFERENCES gap_questions(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id),
    answer TEXT NULL,
    answer_type VARCHAR(30) NOT NULL,
    created_at TIMESTAMP NOT NULL
);

CREATE INDEX idx_projects_user_created ON projects(user_id, created_at DESC);
CREATE INDEX idx_quick_logs_user_created ON quick_logs(user_id, created_at DESC);
CREATE INDEX idx_quick_logs_project ON quick_logs(project_id);
CREATE INDEX idx_project_files_project ON project_files(project_id);
CREATE INDEX idx_analysis_runs_project_created ON analysis_runs(project_id, created_at DESC);
CREATE INDEX idx_experiences_project_created ON experiences(project_id, created_at DESC);
CREATE INDEX idx_evidence_items_project ON evidence_items(project_id);
CREATE INDEX idx_review_sessions_project ON review_sessions(project_id);
CREATE INDEX idx_gap_answers_question ON gap_answers(question_id);
