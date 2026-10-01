ALTER TABLE ai_document_chunks
    RENAME COLUMN source_id TO project_file_id;

ALTER TABLE ai_document_chunks
    RENAME COLUMN file_name TO original_name;

ALTER INDEX IF EXISTS idx_ai_document_chunks_project_source
    RENAME TO idx_ai_document_chunks_project_file;
