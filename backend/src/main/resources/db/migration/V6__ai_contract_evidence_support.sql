ALTER TABLE project_files ADD COLUMN content_hash VARCHAR(64) NULL;

ALTER TABLE analysis_runs
    ADD COLUMN ai_summary TEXT NULL,
    ADD COLUMN information_need VARCHAR(40) NULL,
    ADD COLUMN information_need_reason TEXT NULL,
    ADD COLUMN no_update_reason TEXT NULL,
    ADD COLUMN ai_questions JSONB NULL,
    ADD COLUMN input_source_ids JSONB NULL,
    ADD COLUMN referenced_source_ids JSONB NULL,
    ADD COLUMN source_warnings JSONB NULL,
    ADD COLUMN ai_usage JSONB NULL;

ALTER TABLE experience_candidates
    ADD COLUMN ai_candidate_id UUID NULL,
    ADD COLUMN ai_claims JSONB NULL,
    ADD COLUMN conflicts JSONB NULL;

ALTER TABLE evidence_items
    ADD COLUMN chunk_id UUID NULL,
    ADD COLUMN page_number INTEGER NULL;

CREATE INDEX idx_evidence_items_chunk_id ON evidence_items(chunk_id);
