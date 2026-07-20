"""Add the optional brand packaging workflow identity and artifact.

Revision ID: 20260717_0008
Revises: 20260717_0007
Create Date: 2026-07-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260717_0008"
down_revision: str | None = "20260717_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

AGENT_EXPRESSION = (
    "agent_name IN ('director', 'research', 'strategy', 'production', "
    "'production_coordinator', 'copywriter_agent', 'storyboard_agent', "
    "'video_prompt_agent', 'reviewer', 'brand_packaging')"
)
LEGACY_AGENT_EXPRESSION = (
    "agent_name IN ('director', 'research', 'strategy', 'production', "
    "'production_coordinator', 'copywriter_agent', 'storyboard_agent', "
    "'video_prompt_agent', 'reviewer')"
)
ARTIFACT_EXPRESSION = (
    "artifact_type IN ('creative_brief', 'research', 'strategy', 'copywriting', "
    "'storyboard', 'video_prompt', 'review', 'brand_packaging')"
)
LEGACY_ARTIFACT_EXPRESSION = (
    "artifact_type IN ('creative_brief', 'research', 'strategy', 'copywriting', "
    "'storyboard', 'video_prompt', 'review')"
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
    packaging_runs = bind.execute(
        sa.text("SELECT COUNT(*) FROM agent_runs WHERE agent_name = 'brand_packaging'")
    ).scalar_one()
    packaging_artifacts = bind.execute(
        sa.text(
            "SELECT COUNT(*) FROM content_artifacts "
            "WHERE artifact_type = 'brand_packaging'"
        )
    ).scalar_one()
    if packaging_runs or packaging_artifacts:
        raise RuntimeError("brand_packaging_downgrade_blocked: packaging data still exists")

    with op.batch_alter_table("agent_runs") as batch_op:
        batch_op.drop_constraint("ck_agent_runs_agent_name", type_="check")
        batch_op.create_check_constraint(
            "ck_agent_runs_agent_name",
            LEGACY_AGENT_EXPRESSION,
        )
    with op.batch_alter_table("content_artifacts") as batch_op:
        batch_op.drop_constraint("ck_content_artifacts_artifact_type", type_="check")
        batch_op.create_check_constraint(
            "ck_content_artifacts_artifact_type",
            LEGACY_ARTIFACT_EXPRESSION,
        )
