ALTER TABLE experience_candidates
    ADD COLUMN candidate_type VARCHAR(30) NOT NULL DEFAULT 'NEW',
    ADD COLUMN target_experience_id UUID NULL REFERENCES experiences(id) ON DELETE SET NULL,
    ADD COLUMN match_confidence NUMERIC(5,4) NULL,
    ADD COLUMN match_reason TEXT NULL;

UPDATE experience_candidates
SET status = 'CREATE_NEW'
WHERE status = 'INCLUDED';

ALTER TABLE experience_candidates
    ADD CONSTRAINT ck_experience_candidates_type
        CHECK (candidate_type IN ('NEW', 'ENHANCE_EXISTING')),
    ADD CONSTRAINT ck_experience_candidates_confidence
        CHECK (match_confidence IS NULL OR match_confidence BETWEEN 0 AND 1);

CREATE INDEX idx_experience_candidates_target
    ON experience_candidates(target_experience_id);
