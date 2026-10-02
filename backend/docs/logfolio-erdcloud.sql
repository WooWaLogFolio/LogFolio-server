-- LogFolio ERDCloud import schema
-- Dialect: MySQL-compatible DDL (ERD import only)
-- Runtime PostgreSQL schema: src/main/resources/db/migration/V1__initial_schema.sql

CREATE TABLE `users` (
    `id` CHAR(36) NOT NULL,
    `email` VARCHAR(255) NOT NULL,
    `name` VARCHAR(100) NOT NULL,
    `status` VARCHAR(30) NOT NULL DEFAULT 'ACTIVE',
    `onboarding_completed_at` DATETIME NULL,
    `created_at` DATETIME NOT NULL,
    `updated_at` DATETIME NOT NULL,
    `deleted_at` DATETIME NULL,
    CONSTRAINT `PK_USERS` PRIMARY KEY (`id`),
    CONSTRAINT `UK_USERS_EMAIL` UNIQUE (`email`)
);

CREATE TABLE `auth_accounts` (
    `id` CHAR(36) NOT NULL,
    `user_id` CHAR(36) NOT NULL,
    `provider` VARCHAR(30) NOT NULL,
    `provider_user_id` VARCHAR(255) NOT NULL,
    `provider_email` VARCHAR(255) NULL,
    `password_hash` VARCHAR(255) NULL,
    `created_at` DATETIME NOT NULL,
    CONSTRAINT `PK_AUTH_ACCOUNTS` PRIMARY KEY (`id`),
    CONSTRAINT `UK_AUTH_ACCOUNTS_PROVIDER_USER` UNIQUE (`provider`, `provider_user_id`)
);

CREATE TABLE `user_sessions` (
    `id` CHAR(36) NOT NULL,
    `user_id` CHAR(36) NOT NULL,
    `refresh_token_hash` VARCHAR(255) NOT NULL,
    `expires_at` DATETIME NOT NULL,
    `revoked_at` DATETIME NULL,
    `created_at` DATETIME NOT NULL,
    CONSTRAINT `PK_USER_SESSIONS` PRIMARY KEY (`id`),
    CONSTRAINT `UK_USER_SESSIONS_REFRESH_TOKEN` UNIQUE (`refresh_token_hash`)
);

CREATE TABLE `password_reset_tokens` (
    `id` CHAR(36) NOT NULL,
    `user_id` CHAR(36) NOT NULL,
    `token_hash` VARCHAR(255) NOT NULL,
    `expires_at` DATETIME NOT NULL,
    `used_at` DATETIME NULL,
    `created_at` DATETIME NOT NULL,
    CONSTRAINT `PK_PASSWORD_RESET_TOKENS` PRIMARY KEY (`id`),
    CONSTRAINT `UK_PASSWORD_RESET_TOKEN_HASH` UNIQUE (`token_hash`)
);

CREATE TABLE `projects` (
    `id` CHAR(36) NOT NULL,
    `user_id` CHAR(36) NOT NULL,
    `name` VARCHAR(200) NOT NULL,
    `status` VARCHAR(30) NOT NULL,
    `activity_type` VARCHAR(100) NULL,
    `user_role` VARCHAR(200) NULL,
    `team_size` INT NULL,
    `started_at` DATE NULL,
    `ended_at` DATE NULL,
    `description` VARCHAR(200) NULL,
    `created_at` DATETIME NOT NULL,
    `updated_at` DATETIME NOT NULL,
    `deleted_at` DATETIME NULL,
    CONSTRAINT `PK_PROJECTS` PRIMARY KEY (`id`)
);

CREATE TABLE `project_tags` (
    `project_id` CHAR(36) NOT NULL,
    `display_order` INT NOT NULL,
    `tag` VARCHAR(50) NOT NULL,
    CONSTRAINT `PK_PROJECT_TAGS` PRIMARY KEY (`project_id`, `display_order`),
    CONSTRAINT `UK_PROJECT_TAGS_VALUE` UNIQUE (`project_id`, `tag`)
);

CREATE TABLE `quick_logs` (
    `id` CHAR(36) NOT NULL,
    `user_id` CHAR(36) NOT NULL,
    `project_id` CHAR(36) NULL,
    `content` TEXT NOT NULL,
    `created_at` DATETIME NOT NULL,
    `updated_at` DATETIME NOT NULL,
    `deleted_at` DATETIME NULL,
    CONSTRAINT `PK_QUICK_LOGS` PRIMARY KEY (`id`)
);

CREATE TABLE `project_suggestions` (
    `id` CHAR(36) NOT NULL,
    `quick_log_id` CHAR(36) NOT NULL,
    `project_id` CHAR(36) NOT NULL,
    `confidence` DECIMAL(5,4) NULL,
    `status` VARCHAR(30) NOT NULL,
    `created_at` DATETIME NOT NULL,
    CONSTRAINT `PK_PROJECT_SUGGESTIONS` PRIMARY KEY (`id`),
    CONSTRAINT `UK_PROJECT_SUGGESTIONS_LOG_PROJECT` UNIQUE (`quick_log_id`, `project_id`)
);

CREATE TABLE `project_files` (
    `id` CHAR(36) NOT NULL,
    `project_id` CHAR(36) NOT NULL,
    `user_id` CHAR(36) NOT NULL,
    `original_name` VARCHAR(255) NOT NULL,
    `storage_key` VARCHAR(500) NOT NULL,
    `mime_type` VARCHAR(100) NOT NULL,
    `size_bytes` BIGINT NOT NULL,
    `processing_status` VARCHAR(30) NOT NULL,
    `created_at` DATETIME NOT NULL,
    `deleted_at` DATETIME NULL,
    CONSTRAINT `PK_PROJECT_FILES` PRIMARY KEY (`id`),
    CONSTRAINT `UK_PROJECT_FILES_STORAGE_KEY` UNIQUE (`storage_key`)
);

CREATE TABLE `analysis_runs` (
    `id` CHAR(36) NOT NULL,
    `project_id` CHAR(36) NOT NULL,
    `run_type` VARCHAR(30) NOT NULL,
    `status` VARCHAR(30) NOT NULL,
    `model_version` VARCHAR(100) NULL,
    `started_at` DATETIME NULL,
    `completed_at` DATETIME NULL,
    `created_at` DATETIME NOT NULL,
    CONSTRAINT `PK_ANALYSIS_RUNS` PRIMARY KEY (`id`)
);

CREATE TABLE `analysis_input_files` (
    `analysis_run_id` CHAR(36) NOT NULL,
    `project_file_id` CHAR(36) NOT NULL,
    CONSTRAINT `PK_ANALYSIS_INPUT_FILES` PRIMARY KEY (`analysis_run_id`, `project_file_id`)
);

CREATE TABLE `analysis_input_logs` (
    `analysis_run_id` CHAR(36) NOT NULL,
    `quick_log_id` CHAR(36) NOT NULL,
    CONSTRAINT `PK_ANALYSIS_INPUT_LOGS` PRIMARY KEY (`analysis_run_id`, `quick_log_id`)
);

CREATE TABLE `experience_candidates` (
    `id` CHAR(36) NOT NULL,
    `analysis_run_id` CHAR(36) NOT NULL,
    `merged_into_id` CHAR(36) NULL,
    `candidate_type` VARCHAR(30) NOT NULL DEFAULT 'NEW',
    `target_experience_id` CHAR(36) NULL,
    `match_confidence` DECIMAL(5,4) NULL,
    `match_reason` TEXT NULL,
    `title` VARCHAR(255) NOT NULL,
    `summary` TEXT NULL,
    `draft_content` JSON NULL,
    `status` VARCHAR(30) NOT NULL,
    `created_at` DATETIME NOT NULL,
    CONSTRAINT `PK_EXPERIENCE_CANDIDATES` PRIMARY KEY (`id`)
);

CREATE TABLE `experiences` (
    `id` CHAR(36) NOT NULL,
    `project_id` CHAR(36) NOT NULL,
    `candidate_id` CHAR(36) NULL,
    `title` VARCHAR(255) NOT NULL,
    `summary` TEXT NULL,
    `context` TEXT NULL,
    `contribution` TEXT NULL,
    `decision_reason` TEXT NULL,
    `action` TEXT NULL,
    `result` TEXT NULL,
    `learning` TEXT NULL,
    `status` VARCHAR(30) NOT NULL,
    `version` INT NOT NULL DEFAULT 1,
    `created_at` DATETIME NOT NULL,
    `updated_at` DATETIME NOT NULL,
    `deleted_at` DATETIME NULL,
    CONSTRAINT `PK_EXPERIENCES` PRIMARY KEY (`id`)
);

CREATE TABLE `evidence_items` (
    `id` CHAR(36) NOT NULL,
    `project_id` CHAR(36) NOT NULL,
    `project_file_id` CHAR(36) NULL,
    `quick_log_id` CHAR(36) NULL,
    `excerpt` TEXT NULL,
    `location` VARCHAR(255) NULL,
    `created_at` DATETIME NOT NULL,
    CONSTRAINT `PK_EVIDENCE_ITEMS` PRIMARY KEY (`id`)
);

CREATE TABLE `experience_evidence` (
    `experience_id` CHAR(36) NOT NULL,
    `evidence_item_id` CHAR(36) NOT NULL,
    `section_type` VARCHAR(30) NOT NULL,
    CONSTRAINT `PK_EXPERIENCE_EVIDENCE` PRIMARY KEY (`experience_id`, `evidence_item_id`, `section_type`)
);

CREATE TABLE `review_sessions` (
    `id` CHAR(36) NOT NULL,
    `project_id` CHAR(36) NOT NULL,
    `analysis_run_id` CHAR(36) NULL,
    `status` VARCHAR(30) NOT NULL,
    `started_at` DATETIME NOT NULL,
    `completed_at` DATETIME NULL,
    CONSTRAINT `PK_REVIEW_SESSIONS` PRIMARY KEY (`id`)
);

CREATE TABLE `review_items` (
    `id` CHAR(36) NOT NULL,
    `review_session_id` CHAR(36) NOT NULL,
    `experience_id` CHAR(36) NULL,
    `candidate_id` CHAR(36) NULL,
    `item_type` VARCHAR(40) NOT NULL,
    `proposed_content` TEXT NULL,
    `confirmed_content` TEXT NULL,
    `decision` VARCHAR(30) NOT NULL DEFAULT 'PENDING',
    `display_order` INT NOT NULL,
    `reviewed_at` DATETIME NULL,
    CONSTRAINT `PK_REVIEW_ITEMS` PRIMARY KEY (`id`),
    CONSTRAINT `UK_REVIEW_ITEMS_ORDER` UNIQUE (`review_session_id`, `display_order`)
);

CREATE TABLE `review_item_evidence` (
    `review_item_id` CHAR(36) NOT NULL,
    `evidence_item_id` CHAR(36) NOT NULL,
    CONSTRAINT `PK_REVIEW_ITEM_EVIDENCE` PRIMARY KEY (`review_item_id`, `evidence_item_id`)
);

CREATE TABLE `gap_questions` (
    `id` CHAR(36) NOT NULL,
    `review_item_id` CHAR(36) NULL,
    `experience_id` CHAR(36) NOT NULL,
    `target_section` VARCHAR(30) NOT NULL,
    `question` TEXT NOT NULL,
    `suggested_answers` JSON NULL,
    `display_order` INT NOT NULL,
    `created_at` DATETIME NOT NULL,
    CONSTRAINT `PK_GAP_QUESTIONS` PRIMARY KEY (`id`),
    CONSTRAINT `UK_GAP_QUESTIONS_ORDER` UNIQUE (`experience_id`, `display_order`)
);

CREATE TABLE `gap_answers` (
    `id` CHAR(36) NOT NULL,
    `question_id` CHAR(36) NOT NULL,
    `user_id` CHAR(36) NOT NULL,
    `answer` TEXT NULL,
    `answer_type` VARCHAR(30) NOT NULL,
    `created_at` DATETIME NOT NULL,
    CONSTRAINT `PK_GAP_ANSWERS` PRIMARY KEY (`id`)
);

ALTER TABLE `auth_accounts`
    ADD CONSTRAINT `FK_AUTH_ACCOUNTS_USER`
    FOREIGN KEY (`user_id`) REFERENCES `users` (`id`);

ALTER TABLE `user_sessions`
    ADD CONSTRAINT `FK_USER_SESSIONS_USER`
    FOREIGN KEY (`user_id`) REFERENCES `users` (`id`);

ALTER TABLE `password_reset_tokens`
    ADD CONSTRAINT `FK_PASSWORD_RESET_TOKENS_USER`
    FOREIGN KEY (`user_id`) REFERENCES `users` (`id`);

ALTER TABLE `projects`
    ADD CONSTRAINT `FK_PROJECTS_USER`
    FOREIGN KEY (`user_id`) REFERENCES `users` (`id`);

ALTER TABLE `project_tags`
    ADD CONSTRAINT `FK_PROJECT_TAGS_PROJECT`
    FOREIGN KEY (`project_id`) REFERENCES `projects` (`id`);

ALTER TABLE `quick_logs`
    ADD CONSTRAINT `FK_QUICK_LOGS_USER`
    FOREIGN KEY (`user_id`) REFERENCES `users` (`id`);

ALTER TABLE `quick_logs`
    ADD CONSTRAINT `FK_QUICK_LOGS_PROJECT`
    FOREIGN KEY (`project_id`) REFERENCES `projects` (`id`);

ALTER TABLE `project_suggestions`
    ADD CONSTRAINT `FK_PROJECT_SUGGESTIONS_QUICK_LOG`
    FOREIGN KEY (`quick_log_id`) REFERENCES `quick_logs` (`id`);

ALTER TABLE `project_suggestions`
    ADD CONSTRAINT `FK_PROJECT_SUGGESTIONS_PROJECT`
    FOREIGN KEY (`project_id`) REFERENCES `projects` (`id`);

ALTER TABLE `project_files`
    ADD CONSTRAINT `FK_PROJECT_FILES_PROJECT`
    FOREIGN KEY (`project_id`) REFERENCES `projects` (`id`);

ALTER TABLE `project_files`
    ADD CONSTRAINT `FK_PROJECT_FILES_USER`
    FOREIGN KEY (`user_id`) REFERENCES `users` (`id`);

ALTER TABLE `analysis_runs`
    ADD CONSTRAINT `FK_ANALYSIS_RUNS_PROJECT`
    FOREIGN KEY (`project_id`) REFERENCES `projects` (`id`);

ALTER TABLE `analysis_input_files`
    ADD CONSTRAINT `FK_ANALYSIS_INPUT_FILES_RUN`
    FOREIGN KEY (`analysis_run_id`) REFERENCES `analysis_runs` (`id`);

ALTER TABLE `analysis_input_files`
    ADD CONSTRAINT `FK_ANALYSIS_INPUT_FILES_FILE`
    FOREIGN KEY (`project_file_id`) REFERENCES `project_files` (`id`);

ALTER TABLE `analysis_input_logs`
    ADD CONSTRAINT `FK_ANALYSIS_INPUT_LOGS_RUN`
    FOREIGN KEY (`analysis_run_id`) REFERENCES `analysis_runs` (`id`);

ALTER TABLE `analysis_input_logs`
    ADD CONSTRAINT `FK_ANALYSIS_INPUT_LOGS_LOG`
    FOREIGN KEY (`quick_log_id`) REFERENCES `quick_logs` (`id`);

ALTER TABLE `experience_candidates`
    ADD CONSTRAINT `FK_EXPERIENCE_CANDIDATES_RUN`
    FOREIGN KEY (`analysis_run_id`) REFERENCES `analysis_runs` (`id`);

ALTER TABLE `experience_candidates`
    ADD CONSTRAINT `FK_EXPERIENCE_CANDIDATES_MERGED_INTO`
    FOREIGN KEY (`merged_into_id`) REFERENCES `experience_candidates` (`id`);

ALTER TABLE `experience_candidates`
    ADD CONSTRAINT `FK_EXPERIENCE_CANDIDATES_TARGET_EXPERIENCE`
    FOREIGN KEY (`target_experience_id`) REFERENCES `experiences` (`id`);

ALTER TABLE `experiences`
    ADD CONSTRAINT `FK_EXPERIENCES_PROJECT`
    FOREIGN KEY (`project_id`) REFERENCES `projects` (`id`);

ALTER TABLE `experiences`
    ADD CONSTRAINT `FK_EXPERIENCES_CANDIDATE`
    FOREIGN KEY (`candidate_id`) REFERENCES `experience_candidates` (`id`);

ALTER TABLE `evidence_items`
    ADD CONSTRAINT `FK_EVIDENCE_ITEMS_PROJECT`
    FOREIGN KEY (`project_id`) REFERENCES `projects` (`id`);

ALTER TABLE `evidence_items`
    ADD CONSTRAINT `FK_EVIDENCE_ITEMS_FILE`
    FOREIGN KEY (`project_file_id`) REFERENCES `project_files` (`id`);

ALTER TABLE `evidence_items`
    ADD CONSTRAINT `FK_EVIDENCE_ITEMS_LOG`
    FOREIGN KEY (`quick_log_id`) REFERENCES `quick_logs` (`id`);

ALTER TABLE `experience_evidence`
    ADD CONSTRAINT `FK_EXPERIENCE_EVIDENCE_EXPERIENCE`
    FOREIGN KEY (`experience_id`) REFERENCES `experiences` (`id`);

ALTER TABLE `experience_evidence`
    ADD CONSTRAINT `FK_EXPERIENCE_EVIDENCE_ITEM`
    FOREIGN KEY (`evidence_item_id`) REFERENCES `evidence_items` (`id`);

ALTER TABLE `review_sessions`
    ADD CONSTRAINT `FK_REVIEW_SESSIONS_PROJECT`
    FOREIGN KEY (`project_id`) REFERENCES `projects` (`id`);

ALTER TABLE `review_sessions`
    ADD CONSTRAINT `FK_REVIEW_SESSIONS_RUN`
    FOREIGN KEY (`analysis_run_id`) REFERENCES `analysis_runs` (`id`);

ALTER TABLE `review_items`
    ADD CONSTRAINT `FK_REVIEW_ITEMS_SESSION`
    FOREIGN KEY (`review_session_id`) REFERENCES `review_sessions` (`id`);

ALTER TABLE `review_items`
    ADD CONSTRAINT `FK_REVIEW_ITEMS_EXPERIENCE`
    FOREIGN KEY (`experience_id`) REFERENCES `experiences` (`id`);

ALTER TABLE `review_items`
    ADD CONSTRAINT `FK_REVIEW_ITEMS_CANDIDATE`
    FOREIGN KEY (`candidate_id`) REFERENCES `experience_candidates` (`id`);

ALTER TABLE `review_item_evidence`
    ADD CONSTRAINT `FK_REVIEW_ITEM_EVIDENCE_REVIEW_ITEM`
    FOREIGN KEY (`review_item_id`) REFERENCES `review_items` (`id`);

ALTER TABLE `review_item_evidence`
    ADD CONSTRAINT `FK_REVIEW_ITEM_EVIDENCE_EVIDENCE_ITEM`
    FOREIGN KEY (`evidence_item_id`) REFERENCES `evidence_items` (`id`);

ALTER TABLE `gap_questions`
    ADD CONSTRAINT `FK_GAP_QUESTIONS_REVIEW_ITEM`
    FOREIGN KEY (`review_item_id`) REFERENCES `review_items` (`id`);

ALTER TABLE `gap_questions`
    ADD CONSTRAINT `FK_GAP_QUESTIONS_EXPERIENCE`
    FOREIGN KEY (`experience_id`) REFERENCES `experiences` (`id`);

ALTER TABLE `gap_answers`
    ADD CONSTRAINT `FK_GAP_ANSWERS_QUESTION`
    FOREIGN KEY (`question_id`) REFERENCES `gap_questions` (`id`);

ALTER TABLE `gap_answers`
    ADD CONSTRAINT `FK_GAP_ANSWERS_USER`
    FOREIGN KEY (`user_id`) REFERENCES `users` (`id`);
