ALTER TABLE ai_document_chunks
    RENAME COLUMN project_file_id TO source_id;

ALTER TABLE ai_document_chunks
    RENAME COLUMN original_name TO source_name;

ALTER TABLE ai_document_chunks
    ADD COLUMN source_type VARCHAR(30) NOT NULL DEFAULT 'PROJECT_FILE';

ALTER TABLE ai_document_chunks
    ADD CONSTRAINT ck_ai_document_chunks_source_type
        CHECK (source_type IN ('PROJECT_FILE', 'QUICK_LOG'));

ALTER INDEX IF EXISTS idx_ai_document_chunks_project_file
    RENAME TO idx_ai_document_chunks_project_source;
