CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS ai_document_chunks (
    chunk_id UUID PRIMARY KEY,
    project_id UUID NOT NULL,
    source_id UUID NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    sequence INTEGER NOT NULL CHECK (sequence >= 0),
    page_number INTEGER CHECK (page_number IS NULL OR page_number >= 1),
    section_title TEXT,
    char_start INTEGER NOT NULL CHECK (char_start >= 0),
    char_end INTEGER NOT NULL CHECK (char_end > char_start),
    token_count INTEGER NOT NULL CHECK (token_count > 0),
    content TEXT NOT NULL CHECK (length(content) > 0),
    embedding VECTOR(768) NOT NULL,
    embedding_model VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ai_document_chunks_project_id
    ON ai_document_chunks (project_id);

CREATE INDEX IF NOT EXISTS idx_ai_document_chunks_project_source
    ON ai_document_chunks (project_id, source_id);

-- MVP uses exact cosine search. Add an HNSW vector_cosine_ops index only after
-- production data volume and recall measurements justify approximate search.
