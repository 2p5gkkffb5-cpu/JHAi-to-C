"""Add collaborative studio resources and revision history.

Revision ID: 20260717_0004
Revises: 20260716_0003
Create Date: 2026-07-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260717_0004"
down_revision: str | None = "20260716_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "studio_resources",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("module", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("content_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="draft", nullable=False),
        sa.Column("revision", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_by", sa.String(length=100), nullable=False),
        sa.Column("updated_by", sa.String(length=100), nullable=False),
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
        sa.CheckConstraint(
            "module IN ('ai_video', 'ai_image', 'canvas', 'asset')",
            name="ck_studio_resources_module",
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'ready', 'archived')",
            name="ck_studio_resources_status",
        ),
        sa.CheckConstraint("revision >= 1", name="ck_studio_resources_revision"),
        sa.PrimaryKeyConstraint("id", name="pk_studio_resources"),
    )
    op.create_index(
        "idx_studio_resources_module_updated",
        "studio_resources",
        ["module", "updated_at"],
    )
    op.create_table(
        "studio_resource_revisions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("resource_id", sa.String(length=36), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("content_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("actor", sa.String(length=100), nullable=False),
        sa.Column("change_note", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint("revision >= 1", name="ck_studio_resource_revisions_revision"),
        sa.ForeignKeyConstraint(
            ["resource_id"],
            ["studio_resources.id"],
            name="fk_studio_resource_revisions_resource_id_studio_resources",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_studio_resource_revisions"),
        sa.UniqueConstraint(
            "resource_id", "revision", name="uq_studio_resource_revision"
        ),
    )
    op.create_index(
        "idx_studio_revisions_resource",
        "studio_resource_revisions",
        ["resource_id", "revision"],
    )


def downgrade() -> None:
    op.drop_index("idx_studio_revisions_resource", table_name="studio_resource_revisions")
    op.drop_table("studio_resource_revisions")
    op.drop_index("idx_studio_resources_module_updated", table_name="studio_resources")
    op.drop_table("studio_resources")
