ALTER TABLE ai_document_chunks
    ADD COLUMN content_hash CHAR(64);

ALTER TABLE ai_document_chunks
    ADD CONSTRAINT ck_ai_document_chunks_content_hash
        CHECK (content_hash IS NULL OR content_hash ~ '^[a-f0-9]{64}$');

CREATE INDEX idx_ai_document_chunks_project_content_hash
    ON ai_document_chunks (project_id, content_hash)
    WHERE content_hash IS NOT NULL;
