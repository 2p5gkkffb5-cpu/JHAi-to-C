from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, utc_now


def new_id() -> str:
    return str(uuid4())


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(String(300), default="", server_default="")
    permissions: Mapped[list[str]] = mapped_column(JSON, default=list)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    users: Mapped[list[User]] = relationship(back_populates="role", lazy="raise")


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    phone: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(80))
    password_hash: Mapped[str] = mapped_column(String(255))
    role_id: Mapped[str] = mapped_column(ForeignKey("roles.id", ondelete="RESTRICT"), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("1"))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    role: Mapped[Role] = relationship(back_populates="users", lazy="raise")
    sessions: Mapped[list[AuthSession]] = relationship(
        back_populates="user", cascade="all, delete-orphan", lazy="raise"
    )
    projects: Mapped[list[ContentProject]] = relationship(back_populates="owner", lazy="raise")


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    __table_args__ = (Index("idx_auth_sessions_user_expires", "user_id", "expires_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, server_default=text("CURRENT_TIMESTAMP")
    )

    user: Mapped[User] = relationship(back_populates="sessions")


class UploadedAsset(Base):
    __tablename__ = "uploaded_assets"
    __table_args__ = (
        CheckConstraint("asset_type IN ('image', 'video')", name="asset_type"),
        CheckConstraint("size_bytes > 0", name="size_bytes"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    asset_type: Mapped[str] = mapped_column(String(32), default="image", server_default="image")
    original_name: Mapped[str] = mapped_column(String(200))
    content_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer)
    storage_key: Mapped[str] = mapped_column(String(100), unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, server_default=text("CURRENT_TIMESTAMP")
    )


class ContentProject(Base):
    __tablename__ = "content_projects"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'running', 'waiting_strategy', 'waiting_approval', "
            "'reviewing', "
            "'generating', 'completed', 'failed', 'cancelled')",
            name="status",
        ),
        CheckConstraint("duration_seconds BETWEEN 5 AND 180", name="duration_seconds"),
        CheckConstraint("aspect_ratio IN ('9:16', '16:9', '1:1')", name="aspect_ratio"),
        CheckConstraint(
            "origin IN ('agent', 'ai_video', 'video_clone', 'legacy')",
            name="origin",
        ),
        Index("idx_projects_status_updated", "status", "updated_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    title: Mapped[str] = mapped_column(String(200))
    request_text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="draft", server_default="draft")
    current_node: Mapped[str | None] = mapped_column(String(100))
    target_platform: Mapped[str] = mapped_column(
        String(50), default="douyin", server_default="douyin"
    )
    duration_seconds: Mapped[int] = mapped_column(Integer, default=20, server_default="20")
    aspect_ratio: Mapped[str] = mapped_column(String(10), default="9:16", server_default="9:16")
    blueprint_id: Mapped[str | None] = mapped_column(String(128))
    selected_strategy_id: Mapped[str | None] = mapped_column(String(128))
    requested_mode: Mapped[str] = mapped_column(
        String(32), default="full_creation", server_default="full_creation"
    )
    origin: Mapped[str] = mapped_column(String(32), default="agent", server_default="agent")
    resolved_intent: Mapped[str | None] = mapped_column(String(32))
    final_result: Mapped[dict[str, Any] | None] = mapped_column("final_result_json", JSON)
    error: Mapped[dict[str, Any] | None] = mapped_column("error_json", JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    references: Mapped[list[ProjectReference]] = relationship(
        back_populates="project", cascade="all, delete-orphan", lazy="raise"
    )
    artifacts: Mapped[list[Artifact]] = relationship(
        back_populates="project", cascade="all, delete-orphan", lazy="raise"
    )
    agent_runs: Mapped[list[AgentRun]] = relationship(
        back_populates="project", cascade="all, delete-orphan", lazy="raise"
    )
    events: Mapped[list[ProjectEvent]] = relationship(
        back_populates="project", cascade="all, delete-orphan", lazy="raise"
    )
    video_tasks: Mapped[list[VideoTask]] = relationship(
        back_populates="project", cascade="all, delete-orphan", lazy="raise"
    )
    workflow_jobs: Mapped[list[WorkflowJob]] = relationship(
        back_populates="project", cascade="all, delete-orphan", lazy="raise"
    )
    owner: Mapped[User | None] = relationship(back_populates="projects")


class ProjectReference(Base):
    """Structured snapshot for project references, including uploaded images."""

    __tablename__ = "project_references"
    __table_args__ = (
        CheckConstraint(
            "reference_type IN ('brand', 'product', 'image', 'reference_video', 'blueprint')",
            name="reference_type",
        ),
        CheckConstraint("position >= 0", name="position"),
        UniqueConstraint(
            "project_id",
            "reference_type",
            "reference_id",
            name="uq_project_reference_identity",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("content_projects.id", ondelete="CASCADE"), index=True
    )
    reference_type: Mapped[str] = mapped_column(String(32))
    reference_id: Mapped[str] = mapped_column(String(128))
    label: Mapped[str] = mapped_column(String(200))
    snapshot: Mapped[dict[str, Any]] = mapped_column(
        "snapshot_json", JSON, default=dict, server_default=text("'{}'")
    )
    position: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, server_default=text("CURRENT_TIMESTAMP")
    )

    project: Mapped[ContentProject] = relationship(back_populates="references")


class Artifact(Base):
    __tablename__ = "content_artifacts"
    __table_args__ = (
        CheckConstraint(
            "artifact_type IN ('creative_brief', 'research', 'strategy', 'copywriting', "
            "'storyboard', 'video_prompt', 'review', 'brand_packaging', "
            "'video_clone_analysis', 'video_clone_mapping', 'video_clone_prompt', "
            "'video_clone_review')",
            name="artifact_type",
        ),
        CheckConstraint("version >= 1", name="version"),
        UniqueConstraint(
            "project_id", "artifact_type", "version", name="uq_project_artifact_version"
        ),
        Index("idx_artifacts_project_type", "project_id", "artifact_type", "version"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("content_projects.id", ondelete="CASCADE"))
    artifact_type: Mapped[str] = mapped_column(String(32))
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    content: Mapped[dict[str, Any]] = mapped_column("content_json", JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, server_default=text("CURRENT_TIMESTAMP")
    )

    project: Mapped[ContentProject] = relationship(back_populates="artifacts")


class AgentRun(Base):
    __tablename__ = "agent_runs"
    __table_args__ = (
        CheckConstraint(
            "agent_name IN ('director', 'research', 'strategy', 'production', "
            "'production_coordinator', 'copywriter_agent', 'storyboard_agent', "
            "'video_prompt_agent', 'reviewer', 'brand_packaging', "
            "'video_clone_analysis', 'video_clone_mapping', 'video_clone_prompt', "
            "'video_clone_review')",
            name="agent_name",
        ),
        CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'needs_action', 'failed', 'cancelled')",
            name="status",
        ),
        CheckConstraint("attempt >= 1", name="attempt"),
        Index("idx_agent_runs_project_created", "project_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("content_projects.id", ondelete="CASCADE"))
    agent_name: Mapped[str] = mapped_column(String(32))
    node_name: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(32), default="pending", server_default="pending")
    attempt: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    input_data: Mapped[dict[str, Any] | None] = mapped_column("input_json", JSON)
    output_data: Mapped[dict[str, Any] | None] = mapped_column("output_json", JSON)
    error: Mapped[dict[str, Any] | None] = mapped_column("error_json", JSON)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, server_default=text("CURRENT_TIMESTAMP")
    )

    project: Mapped[ContentProject] = relationship(back_populates="agent_runs")


class ProjectEvent(Base):
    __tablename__ = "project_events"
    __table_args__ = (Index("idx_project_events_project_id", "project_id", "id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("content_projects.id", ondelete="CASCADE"))
    event_type: Mapped[str] = mapped_column(String(100))
    node_name: Mapped[str | None] = mapped_column(String(100))
    payload: Mapped[dict[str, Any]] = mapped_column(
        "payload_json", JSON, default=dict, server_default=text("'{}'")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, server_default=text("CURRENT_TIMESTAMP")
    )

    project: Mapped[ContentProject] = relationship(back_populates="events")


class VideoTask(Base):
    __tablename__ = "video_tasks"
    __table_args__ = (
        CheckConstraint("is_mock IN (0, 1)", name="is_mock"),
        CheckConstraint(
            "status IN ('queued', 'processing', 'completed', 'failed', 'cancelled')",
            name="status",
        ),
        CheckConstraint("progress IS NULL OR progress BETWEEN 0 AND 1", name="progress"),
        Index("idx_video_tasks_project_status", "project_id", "status"),
        Index(
            "uq_video_tasks_provider_external_id",
            "provider",
            "external_task_id",
            unique=True,
            sqlite_where=text("external_task_id IS NOT NULL"),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("content_projects.id", ondelete="CASCADE"))
    provider: Mapped[str] = mapped_column(String(100))
    is_mock: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("1"))
    external_task_id: Mapped[str | None] = mapped_column(String(256))
    status: Mapped[str] = mapped_column(String(32), default="queued", server_default="queued")
    request_data: Mapped[dict[str, Any]] = mapped_column("request_json", JSON)
    progress: Mapped[float | None] = mapped_column(Float)
    result_url: Mapped[str | None] = mapped_column(Text)
    error: Mapped[dict[str, Any] | None] = mapped_column("error_json", JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    project: Mapped[ContentProject] = relationship(back_populates="video_tasks")


class WorkflowJob(Base):
    __tablename__ = "workflow_jobs"
    __table_args__ = (
        CheckConstraint(
            "job_type IN ('run_project', 'resume_project', 'poll_video')", name="job_type"
        ),
        CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed', 'cancelled')",
            name="status",
        ),
        CheckConstraint("attempts >= 0", name="attempts"),
        Index("idx_workflow_jobs_claim", "status", "available_at", "locked_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("content_projects.id", ondelete="CASCADE"))
    job_type: Mapped[str] = mapped_column(
        String(32), default="run_project", server_default="run_project"
    )
    status: Mapped[str] = mapped_column(String(32), default="pending", server_default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, server_default=text("CURRENT_TIMESTAMP")
    )
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    resume_payload: Mapped[dict[str, Any] | None] = mapped_column("resume_payload_json", JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    project: Mapped[ContentProject] = relationship(back_populates="workflow_jobs")


class StudioResource(Base):
    __tablename__ = "studio_resources"
    __table_args__ = (
        CheckConstraint(
            "module IN ('ai_video', 'ai_image', 'canvas', 'asset')",
            name="module",
        ),
        CheckConstraint(
            "status IN ('draft', 'ready', 'archived')",
            name="status",
        ),
        CheckConstraint("revision >= 1", name="revision"),
        Index("idx_studio_resources_module_updated", "module", "updated_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    module: Mapped[str] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(String(200))
    content: Mapped[dict[str, Any]] = mapped_column("content_json", JSON)
    status: Mapped[str] = mapped_column(String(32), default="draft", server_default="draft")
    revision: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    created_by: Mapped[str] = mapped_column(String(100), default="anonymous")
    updated_by: Mapped[str] = mapped_column(String(100), default="anonymous")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    revisions: Mapped[list[StudioResourceRevision]] = relationship(
        back_populates="resource", cascade="all, delete-orphan", lazy="raise"
    )


class StudioResourceRevision(Base):
    __tablename__ = "studio_resource_revisions"
    __table_args__ = (
        CheckConstraint("revision >= 1", name="revision"),
        UniqueConstraint("resource_id", "revision", name="uq_studio_resource_revision"),
        Index("idx_studio_revisions_resource", "resource_id", "revision"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    resource_id: Mapped[str] = mapped_column(ForeignKey("studio_resources.id", ondelete="CASCADE"))
    revision: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(200))
    content: Mapped[dict[str, Any]] = mapped_column("content_json", JSON)
    status: Mapped[str] = mapped_column(String(32))
    actor: Mapped[str] = mapped_column(String(100))
    change_note: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, server_default=text("CURRENT_TIMESTAMP")
    )

    resource: Mapped[StudioResource] = relationship(back_populates="revisions")
