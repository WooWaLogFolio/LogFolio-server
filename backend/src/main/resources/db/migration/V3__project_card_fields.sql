ALTER TABLE projects ADD COLUMN IF NOT EXISTS team_size INTEGER NULL;

ALTER TABLE projects
    ADD CONSTRAINT ck_projects_team_size CHECK (team_size IS NULL OR team_size > 0);

CREATE TABLE IF NOT EXISTS project_tags (
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    display_order INTEGER NOT NULL,
    tag VARCHAR(50) NOT NULL,
    PRIMARY KEY (project_id, display_order),
    CONSTRAINT uk_project_tags_value UNIQUE (project_id, tag)
);
