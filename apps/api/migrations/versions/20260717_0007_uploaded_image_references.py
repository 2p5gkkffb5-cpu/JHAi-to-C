"""Add uploaded image assets and image project references.

Revision ID: 20260717_0007
Revises: 20260717_0006
Create Date: 2026-07-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260717_0007"
down_revision: str | None = "20260717_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MEMBER_ROLE_ID = "00000000-0000-0000-0000-000000000002"
MEMBER_PERMISSIONS = [
    "content_projects:create",
    "content_projects:read",
    "content_projects:update",
    "content_projects:cancel",
    "images:generate",
    "assets:upload",
]


def upgrade() -> None:
    op.create_table(
        "uploaded_assets",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("owner_id", sa.String(length=36), nullable=True),
        sa.Column("asset_type", sa.String(length=32), server_default="image", nullable=False),
        sa.Column("original_name", sa.String(length=200), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("storage_key", sa.String(length=100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint("asset_type IN ('image')", name="ck_uploaded_assets_asset_type"),
        sa.CheckConstraint("size_bytes > 0", name="ck_uploaded_assets_size_bytes"),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name="fk_uploaded_assets_owner_id_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_uploaded_assets"),
        sa.UniqueConstraint("storage_key", name="uq_uploaded_assets_storage_key"),
    )
    op.create_index("ix_uploaded_assets_owner_id", "uploaded_assets", ["owner_id"])

    with op.batch_alter_table("project_references") as batch_op:
        batch_op.drop_constraint("ck_project_references_reference_type", type_="check")
        batch_op.create_check_constraint(
            "ck_project_references_reference_type",
            "reference_type IN ('brand', 'product', 'image', 'reference_video', 'blueprint')",
        )

    _set_member_permissions(MEMBER_PERMISSIONS)


def downgrade() -> None:
    _set_member_permissions(MEMBER_PERMISSIONS[:-1])
    with op.batch_alter_table("project_references") as batch_op:
        batch_op.drop_constraint("ck_project_references_reference_type", type_="check")
        batch_op.create_check_constraint(
            "ck_project_references_reference_type",
            "reference_type IN ('brand', 'product', 'reference_video', 'blueprint')",
        )
    op.drop_index("ix_uploaded_assets_owner_id", table_name="uploaded_assets")
    op.drop_table("uploaded_assets")


def _set_member_permissions(permissions: list[str]) -> None:
    roles = sa.table(
        "roles",
        sa.column("id", sa.String),
        sa.column("permissions", sa.JSON),
    )
    op.execute(
        roles.update().where(roles.c.id == MEMBER_ROLE_ID).values(permissions=permissions)
    )
