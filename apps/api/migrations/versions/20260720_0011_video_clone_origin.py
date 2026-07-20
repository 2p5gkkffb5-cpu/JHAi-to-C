"""Add an isolated origin for video clone projects.

Revision ID: 20260720_0011
Revises: 20260720_0010
Create Date: 2026-07-20
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260720_0011"
down_revision: str | None = "20260720_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("content_projects") as batch_op:
        batch_op.drop_constraint("ck_content_projects_origin", type_="check")
        batch_op.create_check_constraint(
            "ck_content_projects_origin",
            "origin IN ('agent', 'ai_video', 'video_clone', 'legacy')",
        )


def downgrade() -> None:
    op.execute("UPDATE content_projects SET origin = 'ai_video' WHERE origin = 'video_clone'")
    with op.batch_alter_table("content_projects") as batch_op:
        batch_op.drop_constraint("ck_content_projects_origin", type_="check")
        batch_op.create_check_constraint(
            "ck_content_projects_origin",
            "origin IN ('agent', 'ai_video', 'legacy')",
        )
