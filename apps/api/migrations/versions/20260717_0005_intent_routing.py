"""Add requested and resolved intent fields to content projects.

Revision ID: 20260717_0005
Revises: 20260717_0004
Create Date: 2026-07-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260717_0005"
down_revision: str | None = "20260717_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "content_projects",
        sa.Column(
            "requested_mode",
            sa.String(length=32),
            server_default="full_creation",
            nullable=False,
        ),
    )
    op.add_column(
        "content_projects",
        sa.Column("resolved_intent", sa.String(length=32), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("content_projects", "resolved_intent")
    op.drop_column("content_projects", "requested_mode")
