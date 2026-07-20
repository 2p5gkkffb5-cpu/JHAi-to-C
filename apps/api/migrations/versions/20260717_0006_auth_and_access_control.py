"""Add users, sessions, roles, permissions, and project ownership.

Revision ID: 20260717_0006
Revises: 20260717_0005
Create Date: 2026-07-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260717_0006"
down_revision: str | None = "20260717_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ADMIN_ROLE_ID = "00000000-0000-0000-0000-000000000001"
MEMBER_ROLE_ID = "00000000-0000-0000-0000-000000000002"


def upgrade() -> None:
    op.create_table(
        "roles",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=300), server_default="", nullable=False),
        sa.Column("permissions", sa.JSON(), nullable=False),
        sa.Column("is_system", sa.Boolean(), server_default=sa.text("0"), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name="pk_roles"),
        sa.UniqueConstraint("code", name="uq_roles_code"),
    )
    op.create_index("ix_roles_code", "roles", ["code"])
    role_table = sa.table(
        "roles",
        sa.column("id", sa.String),
        sa.column("code", sa.String),
        sa.column("name", sa.String),
        sa.column("description", sa.String),
        sa.column("permissions", sa.JSON),
        sa.column("is_system", sa.Boolean),
    )
    op.bulk_insert(
        role_table,
        [
            {
                "id": ADMIN_ROLE_ID,
                "code": "admin",
                "name": "管理员",
                "description": "拥有全部功能和权限配置能力",
                "permissions": ["*"],
                "is_system": True,
            },
            {
                "id": MEMBER_ROLE_ID,
                "code": "member",
                "name": "成员",
                "description": "可使用日常创作能力，仅访问本人项目",
                "permissions": [
                    "content_projects:create",
                    "content_projects:read",
                    "content_projects:update",
                    "content_projects:cancel",
                    "images:generate",
                ],
                "is_system": True,
            },
        ],
    )

    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=False),
        sa.Column("display_name", sa.String(length=80), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role_id", sa.String(length=36), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("1"), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["role_id"], ["roles.id"], name="fk_users_role_id_roles", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("phone", name="uq_users_phone"),
    )
    op.create_index("ix_users_phone", "users", ["phone"])
    op.create_index("ix_users_role_id", "users", ["role_id"])

    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_auth_sessions_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_auth_sessions"),
        sa.UniqueConstraint("token_hash", name="uq_auth_sessions_token_hash"),
    )
    op.create_index("ix_auth_sessions_token_hash", "auth_sessions", ["token_hash"])
    op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"])
    op.create_index("idx_auth_sessions_user_expires", "auth_sessions", ["user_id", "expires_at"])

    with op.batch_alter_table("content_projects") as batch_op:
        batch_op.add_column(sa.Column("owner_id", sa.String(length=36)))
        batch_op.create_foreign_key(
            "fk_content_projects_owner_id_users",
            "users",
            ["owner_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index("ix_content_projects_owner_id", ["owner_id"])


def downgrade() -> None:
    with op.batch_alter_table("content_projects") as batch_op:
        batch_op.drop_index("ix_content_projects_owner_id")
        batch_op.drop_constraint("fk_content_projects_owner_id_users", type_="foreignkey")
        batch_op.drop_column("owner_id")
    op.drop_index("idx_auth_sessions_user_expires", table_name="auth_sessions")
    op.drop_index("ix_auth_sessions_user_id", table_name="auth_sessions")
    op.drop_index("ix_auth_sessions_token_hash", table_name="auth_sessions")
    op.drop_table("auth_sessions")
    op.drop_index("ix_users_role_id", table_name="users")
    op.drop_index("ix_users_phone", table_name="users")
    op.drop_table("users")
    op.drop_index("ix_roles_code", table_name="roles")
    op.drop_table("roles")
