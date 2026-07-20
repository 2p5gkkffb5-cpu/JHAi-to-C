"""Separate Agent projects from AI video generations.

Revision ID: 20260720_0010
Revises: 20260720_0009
Create Date: 2026-07-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260720_0010"
down_revision: str | None = "20260720_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("content_projects") as batch_op:
        batch_op.add_column(
            sa.Column(
                "origin",
                sa.String(length=32),
                nullable=True,
            )
        )

    # Older Agent and standalone-video records both used
    # requested_mode=video_generation, so their source cannot be reconstructed
    # safely. Preserve that ambiguity explicitly instead of leaking history
    # into either newly isolated workspace.
    op.execute("UPDATE content_projects SET origin = 'legacy' WHERE origin IS NULL")

    with op.batch_alter_table("content_projects") as batch_op:
        batch_op.alter_column(
            "origin",
            existing_type=sa.String(length=32),
            nullable=False,
            server_default="agent",
        )
        batch_op.create_check_constraint(
            "ck_content_projects_origin",
            "origin IN ('agent', 'ai_video', 'legacy')",
        )


def downgrade() -> None:
    with op.batch_alter_table("content_projects") as batch_op:
        batch_op.drop_constraint("ck_content_projects_origin", type_="check")
        batch_op.drop_column("origin")
