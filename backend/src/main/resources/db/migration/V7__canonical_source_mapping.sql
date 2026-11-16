ALTER TABLE project_files
    ADD COLUMN canonical_source_id UUID NULL;

ALTER TABLE quick_logs
    ADD COLUMN canonical_source_id UUID NULL;

CREATE INDEX idx_project_files_canonical_source ON project_files(canonical_source_id);
CREATE INDEX idx_quick_logs_canonical_source ON quick_logs(canonical_source_id);
