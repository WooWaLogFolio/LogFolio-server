ALTER TABLE analysis_runs
    ADD COLUMN error_code VARCHAR(80),
    ADD COLUMN error_message TEXT,
    ADD COLUMN failure_stage VARCHAR(80);
