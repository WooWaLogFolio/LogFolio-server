#!/bin/sh
set -eu

psql -v ON_ERROR_STOP=1 <<'SQL'
CREATE TABLE IF NOT EXISTS ai_schema_migrations (
    version VARCHAR(255) PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

DO $$
BEGIN
    IF to_regclass('public.ai_document_chunks') IS NOT NULL THEN
        INSERT INTO ai_schema_migrations(version)
        VALUES ('001_create_ai_document_chunks.sql')
        ON CONFLICT DO NOTHING;

        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'ai_document_chunks'
              AND column_name = 'project_file_id'
        ) OR EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'ai_document_chunks'
              AND column_name = 'source_type'
        ) THEN
            INSERT INTO ai_schema_migrations(version)
            VALUES ('002_align_chunk_columns_with_project_files.sql')
            ON CONFLICT DO NOTHING;
        END IF;

        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'ai_document_chunks'
              AND column_name = 'source_type'
        ) THEN
            INSERT INTO ai_schema_migrations(version)
            VALUES ('003_support_unified_sources.sql')
            ON CONFLICT DO NOTHING;
        END IF;

        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'ai_document_chunks'
              AND column_name = 'content_hash'
        ) THEN
            INSERT INTO ai_schema_migrations(version)
            VALUES ('004_add_source_content_hash.sql')
            ON CONFLICT DO NOTHING;
        END IF;
    END IF;
END
$$;
SQL

for migration in /migrations/sql/*.sql; do
    version=$(basename "$migration")
    applied=$(psql -v ON_ERROR_STOP=1 -tAc \
        "SELECT 1 FROM ai_schema_migrations WHERE version = '$version'")
    if [ "$applied" = "1" ]; then
        echo "Migration already applied: $version"
        continue
    fi

    echo "Applying migration: $version"
    psql -v ON_ERROR_STOP=1 -f "$migration"
    psql -v ON_ERROR_STOP=1 -c \
        "INSERT INTO ai_schema_migrations(version) VALUES ('$version')"
done
