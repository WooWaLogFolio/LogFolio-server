ALTER TABLE quick_logs
    ADD COLUMN processing_status VARCHAR(30) NULL;

ALTER TABLE quick_logs
    ADD CONSTRAINT ck_quick_logs_processing_status
        CHECK (processing_status IS NULL OR processing_status IN ('PROCESSING', 'INDEXED', 'FAILED'));

ALTER TABLE project_files
    DROP CONSTRAINT IF EXISTS ck_project_files_processing_status;

ALTER TABLE project_files
    ADD CONSTRAINT ck_project_files_processing_status
        CHECK (processing_status IN ('UPLOADED', 'PROCESSING', 'PROCESSED', 'INDEXED', 'FAILED'));
