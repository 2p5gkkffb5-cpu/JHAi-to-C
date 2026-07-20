"""Create Phase 1 financing Demo persistence schema.

Revision ID: 20260716_0001
Revises:
Create Date: 2026-07-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260716_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "content_projects",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("request_text", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="draft", nullable=False),
        sa.Column("current_node", sa.String(length=100), nullable=True),
        sa.Column("target_platform", sa.String(length=50), server_default="douyin", nullable=False),
        sa.Column("duration_seconds", sa.Integer(), server_default="20", nullable=False),
        sa.Column("aspect_ratio", sa.String(length=10), server_default="9:16", nullable=False),
        sa.Column("blueprint_id", sa.String(length=128), nullable=True),
        sa.Column("selected_strategy_id", sa.String(length=128), nullable=True),
        sa.Column("final_result_json", sa.JSON(), nullable=True),
        sa.Column("error_json", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "aspect_ratio IN ('9:16', '16:9', '1:1')",
            name="ck_content_projects_aspect_ratio",
        ),
        sa.CheckConstraint(
            "duration_seconds BETWEEN 5 AND 180", name="ck_content_projects_duration_seconds"
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'running', 'waiting_strategy', 'reviewing', "
            "'generating', 'completed', 'failed', 'cancelled')",
            name="ck_content_projects_status",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_content_projects"),
    )
    op.create_index("idx_projects_status_updated", "content_projects", ["status", "updated_at"])

    op.create_table(
        "project_references",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("reference_type", sa.String(length=32), nullable=False),
        sa.Column("reference_id", sa.String(length=128), nullable=False),
        sa.Column("label", sa.String(length=200), nullable=False),
        sa.Column("snapshot_json", sa.JSON(), server_default=sa.text("'{}'"), nullable=False),
        sa.Column("position", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint("position >= 0", name="ck_project_references_position"),
        sa.CheckConstraint(
            "reference_type IN ('brand', 'product', 'reference_video', 'blueprint')",
            name="ck_project_references_reference_type",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["content_projects.id"],
            name="fk_project_references_project_id_content_projects",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_project_references"),
        sa.UniqueConstraint(
            "project_id",
            "reference_type",
            "reference_id",
            name="uq_project_reference_identity",
        ),
    )
    op.create_index("ix_project_references_project_id", "project_references", ["project_id"])

    op.create_table(
        "content_artifacts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("artifact_type", sa.String(length=32), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("content_json", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "artifact_type IN ('creative_brief', 'research', 'strategy', 'copywriting', "
            "'storyboard', 'video_prompt', 'review')",
            name="ck_content_artifacts_artifact_type",
        ),
        sa.CheckConstraint("version >= 1", name="ck_content_artifacts_version"),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["content_projects.id"],
            name="fk_content_artifacts_project_id_content_projects",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_content_artifacts"),
        sa.UniqueConstraint(
            "project_id", "artifact_type", "version", name="uq_project_artifact_version"
        ),
    )
    op.create_index(
        "idx_artifacts_project_type",
        "content_artifacts",
        ["project_id", "artifact_type", "version"],
    )

    op.create_table(
        "agent_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("agent_name", sa.String(length=32), nullable=False),
        sa.Column("node_name", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="pending", nullable=False),
        sa.Column("attempt", sa.Integer(), server_default="1", nullable=False),
        sa.Column("input_json", sa.JSON(), nullable=True),
        sa.Column("output_json", sa.JSON(), nullable=True),
        sa.Column("error_json", sa.JSON(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint("attempt >= 1", name="ck_agent_runs_attempt"),
        sa.CheckConstraint(
            "agent_name IN ('director', 'research', 'strategy', 'production', 'reviewer')",
            name="ck_agent_runs_agent_name",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'needs_action', 'failed')",
            name="ck_agent_runs_status",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["content_projects.id"],
            name="fk_agent_runs_project_id_content_projects",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_agent_runs"),
    )
    op.create_index("idx_agent_runs_project_created", "agent_runs", ["project_id", "created_at"])

    op.create_table(
        "project_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("node_name", sa.String(length=100), nullable=True),
        sa.Column("payload_json", sa.JSON(), server_default=sa.text("'{}'"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["content_projects.id"],
            name="fk_project_events_project_id_content_projects",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_project_events"),
    )
    op.create_index("idx_project_events_project_id", "project_events", ["project_id", "id"])

    op.create_table(
        "video_tasks",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("is_mock", sa.Boolean(), server_default=sa.text("1"), nullable=False),
        sa.Column("external_task_id", sa.String(length=256), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="queued", nullable=False),
        sa.Column("request_json", sa.JSON(), nullable=False),
        sa.Column("progress", sa.Float(), nullable=True),
        sa.Column("result_url", sa.Text(), nullable=True),
        sa.Column("error_json", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint("is_mock IN (0, 1)", name="ck_video_tasks_is_mock"),
        sa.CheckConstraint(
            "progress IS NULL OR progress BETWEEN 0 AND 1", name="ck_video_tasks_progress"
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'processing', 'completed', 'failed', 'cancelled')",
            name="ck_video_tasks_status",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["content_projects.id"],
            name="fk_video_tasks_project_id_content_projects",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_video_tasks"),
    )
    op.create_index("idx_video_tasks_project_status", "video_tasks", ["project_id", "status"])
    op.create_index(
        "uq_video_tasks_provider_external_id",
        "video_tasks",
        ["provider", "external_task_id"],
        unique=True,
        sqlite_where=sa.text("external_task_id IS NOT NULL"),
    )

    op.create_table(
        "workflow_jobs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("job_type", sa.String(length=32), server_default="run_project", nullable=False),
        sa.Column("status", sa.String(length=32), server_default="pending", nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "available_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint("attempts >= 0", name="ck_workflow_jobs_attempts"),
        sa.CheckConstraint(
            "job_type IN ('run_project', 'resume_project', 'poll_video')",
            name="ck_workflow_jobs_job_type",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed', 'cancelled')",
            name="ck_workflow_jobs_status",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["content_projects.id"],
            name="fk_workflow_jobs_project_id_content_projects",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_workflow_jobs"),
    )
    op.create_index(
        "idx_workflow_jobs_claim",
        "workflow_jobs",
        ["status", "available_at", "locked_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_workflow_jobs_claim", table_name="workflow_jobs")
    op.drop_table("workflow_jobs")
    op.drop_index("uq_video_tasks_provider_external_id", table_name="video_tasks")
    op.drop_index("idx_video_tasks_project_status", table_name="video_tasks")
    op.drop_table("video_tasks")
    op.drop_index("idx_project_events_project_id", table_name="project_events")
    op.drop_table("project_events")
    op.drop_index("idx_agent_runs_project_created", table_name="agent_runs")
    op.drop_table("agent_runs")
    op.drop_index("idx_artifacts_project_type", table_name="content_artifacts")
    op.drop_table("content_artifacts")
    op.drop_index("ix_project_references_project_id", table_name="project_references")
    op.drop_table("project_references")
    op.drop_index("idx_projects_status_updated", table_name="content_projects")
    op.drop_table("content_projects")
