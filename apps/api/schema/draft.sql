-- Phase 0 database schema draft for the single-instance financing Demo MVP.
-- This file is intentionally not an Alembic migration.

PRAGMA foreign_keys = ON;

CREATE TABLE content_projects (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    request_text TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN (
            'draft',
            'running',
            'waiting_strategy',
            'waiting_approval',
            'reviewing',
            'generating',
            'completed',
            'failed',
            'cancelled'
        )),
    current_node TEXT,
    target_platform TEXT NOT NULL DEFAULT 'douyin',
    duration_seconds INTEGER NOT NULL DEFAULT 20
        CHECK (duration_seconds BETWEEN 5 AND 180),
    aspect_ratio TEXT NOT NULL DEFAULT '9:16'
        CHECK (aspect_ratio IN ('9:16', '16:9', '1:1')),
    blueprint_id TEXT,
    selected_strategy_id TEXT,
    final_result_json TEXT CHECK (
        final_result_json IS NULL OR json_valid(final_result_json)
    ),
    error_json TEXT CHECK (
        error_json IS NULL OR json_valid(error_json)
    ),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    started_at TEXT,
    completed_at TEXT
);

CREATE TABLE project_references (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    reference_type TEXT NOT NULL
        CHECK (reference_type IN ('brand', 'product', 'reference_video', 'blueprint')),
    reference_id TEXT NOT NULL,
    label TEXT NOT NULL,
    snapshot_json TEXT NOT NULL DEFAULT '{}'
        CHECK (json_valid(snapshot_json)),
    position INTEGER NOT NULL DEFAULT 0 CHECK (position >= 0),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (project_id) REFERENCES content_projects(id) ON DELETE CASCADE,
    UNIQUE (project_id, reference_type, reference_id)
);

CREATE TABLE content_artifacts (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    artifact_type TEXT NOT NULL
        CHECK (artifact_type IN (
            'creative_brief',
            'research',
            'strategy',
            'copywriting',
            'storyboard',
            'video_prompt',
            'review'
        )),
    version INTEGER NOT NULL DEFAULT 1 CHECK (version >= 1),
    content_json TEXT NOT NULL CHECK (json_valid(content_json)),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (project_id) REFERENCES content_projects(id) ON DELETE CASCADE,
    UNIQUE (project_id, artifact_type, version)
);

CREATE TABLE agent_runs (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    agent_name TEXT NOT NULL
        CHECK (agent_name IN ('director', 'research', 'strategy', 'production', 'reviewer')),
    node_name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (
            status IN ('pending', 'running', 'completed', 'needs_action', 'failed', 'cancelled')
        ),
    attempt INTEGER NOT NULL DEFAULT 1 CHECK (attempt >= 1),
    input_json TEXT CHECK (input_json IS NULL OR json_valid(input_json)),
    output_json TEXT CHECK (output_json IS NULL OR json_valid(output_json)),
    error_json TEXT CHECK (error_json IS NULL OR json_valid(error_json)),
    started_at TEXT,
    completed_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (project_id) REFERENCES content_projects(id) ON DELETE CASCADE
);

CREATE TABLE project_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    node_name TEXT,
    payload_json TEXT NOT NULL DEFAULT '{}'
        CHECK (json_valid(payload_json)),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (project_id) REFERENCES content_projects(id) ON DELETE CASCADE
);

CREATE TABLE video_tasks (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    is_mock INTEGER NOT NULL DEFAULT 1 CHECK (is_mock IN (0, 1)),
    external_task_id TEXT,
    status TEXT NOT NULL DEFAULT 'queued'
        CHECK (status IN ('queued', 'processing', 'completed', 'failed', 'cancelled')),
    request_json TEXT NOT NULL CHECK (json_valid(request_json)),
    progress REAL CHECK (progress IS NULL OR progress BETWEEN 0 AND 1),
    result_url TEXT,
    error_json TEXT CHECK (error_json IS NULL OR json_valid(error_json)),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (project_id) REFERENCES content_projects(id) ON DELETE CASCADE
);

CREATE TABLE workflow_jobs (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    job_type TEXT NOT NULL DEFAULT 'run_project'
        CHECK (job_type IN ('run_project', 'resume_project', 'poll_video')),
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled')),
    attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    available_at TEXT NOT NULL DEFAULT (datetime('now')),
    locked_at TEXT,
    last_error TEXT,
    resume_payload_json JSON,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (project_id) REFERENCES content_projects(id) ON DELETE CASCADE
);

CREATE INDEX idx_projects_status_updated
    ON content_projects(status, updated_at);

CREATE INDEX idx_agent_runs_project_created
    ON agent_runs(project_id, created_at);

CREATE INDEX idx_project_events_project_id
    ON project_events(project_id, id);

CREATE INDEX idx_video_tasks_project_status
    ON video_tasks(project_id, status);

CREATE INDEX idx_workflow_jobs_claim
    ON workflow_jobs(status, available_at, locked_at);

CREATE UNIQUE INDEX uq_video_tasks_provider_external_id
    ON video_tasks(provider, external_task_id)
    WHERE external_task_id IS NOT NULL;
