"""Add video clone workflow Agents and artifacts.

Revision ID: 20260720_0012
Revises: 20260720_0011
Create Date: 2026-07-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260720_0012"
down_revision: str | None = "20260720_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

AGENT_EXPRESSION = (
    "agent_name IN ('director', 'research', 'strategy', 'production', "
    "'production_coordinator', 'copywriter_agent', 'storyboard_agent', "
    "'video_prompt_agent', 'reviewer', 'brand_packaging', "
    "'video_clone_analysis', 'video_clone_mapping', 'video_clone_prompt', "
    "'video_clone_review')"
)
LEGACY_AGENT_EXPRESSION = (
    "agent_name IN ('director', 'research', 'strategy', 'production', "
    "'production_coordinator', 'copywriter_agent', 'storyboard_agent', "
    "'video_prompt_agent', 'reviewer', 'brand_packaging')"
)
ARTIFACT_EXPRESSION = (
    "artifact_type IN ('creative_brief', 'research', 'strategy', 'copywriting', "
    "'storyboard', 'video_prompt', 'review', 'brand_packaging', "
    "'video_clone_analysis', 'video_clone_mapping', 'video_clone_prompt', "
    "'video_clone_review')"
)
LEGACY_ARTIFACT_EXPRESSION = (
    "artifact_type IN ('creative_brief', 'research', 'strategy', 'copywriting', "
    "'storyboard', 'video_prompt', 'review', 'brand_packaging')"
)


def upgrade() -> None:
    with op.batch_alter_table("agent_runs") as batch_op:
        batch_op.drop_constraint("ck_agent_runs_agent_name", type_="check")
        batch_op.create_check_constraint("ck_agent_runs_agent_name", AGENT_EXPRESSION)
    with op.batch_alter_table("content_artifacts") as batch_op:
        batch_op.drop_constraint("ck_content_artifacts_artifact_type", type_="check")
        batch_op.create_check_constraint(
            "ck_content_artifacts_artifact_type",
            ARTIFACT_EXPRESSION,
        )


def downgrade() -> None:
    bind = op.get_bind()
    clone_runs = bind.execute(
        sa.text("SELECT COUNT(*) FROM agent_runs WHERE agent_name LIKE 'video_clone_%'")
    ).scalar_one()
    clone_artifacts = bind.execute(
        sa.text(
            "SELECT COUNT(*) FROM content_artifacts "
            "WHERE artifact_type LIKE 'video_clone_%'"
        )
    ).scalar_one()
    if clone_runs or clone_artifacts:
        raise RuntimeError("video_clone_downgrade_blocked: workflow data still exists")

    with op.batch_alter_table("agent_runs") as batch_op:
        batch_op.drop_constraint("ck_agent_runs_agent_name", type_="check")
        batch_op.create_check_constraint("ck_agent_runs_agent_name", LEGACY_AGENT_EXPRESSION)
    with op.batch_alter_table("content_artifacts") as batch_op:
        batch_op.drop_constraint("ck_content_artifacts_artifact_type", type_="check")
        batch_op.create_check_constraint(
            "ck_content_artifacts_artifact_type",
            LEGACY_ARTIFACT_EXPRESSION,
        )
