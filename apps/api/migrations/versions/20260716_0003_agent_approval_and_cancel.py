"""Add Agent approval waits, cancellation, and persisted resume payloads.

Revision ID: 20260716_0003
Revises: 20260716_0002
Create Date: 2026-07-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260716_0003"
down_revision: str | None = "20260716_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PROJECT_STATUS_CONSTRAINT = "ck_content_projects_ck_content_projects_status"
_AGENT_STATUS_CONSTRAINT = "ck_agent_runs_ck_agent_runs_status"
_OLD_PROJECT_STATUS = (
    "status IN ('draft', 'running', 'waiting_strategy', 'reviewing', "
    "'generating', 'completed', 'failed', 'cancelled')"
)
_NEW_PROJECT_STATUS = (
    "status IN ('draft', 'running', 'waiting_strategy', 'waiting_approval', "
    "'reviewing', 'generating', 'completed', 'failed', 'cancelled')"
)
_OLD_AGENT_STATUS = "status IN ('pending', 'running', 'completed', 'needs_action', 'failed')"
_NEW_AGENT_STATUS = (
    "status IN ('pending', 'running', 'completed', 'needs_action', 'failed', 'cancelled')"
)


def _replace_check(table: str, name: str, expression: str) -> None:
    final_name = op.f(name)
    with op.batch_alter_table(table) as batch_op:
        batch_op.drop_constraint(final_name, type_="check")
        batch_op.create_check_constraint(final_name, expression)


def upgrade() -> None:
    _replace_check("content_projects", _PROJECT_STATUS_CONSTRAINT, _NEW_PROJECT_STATUS)
    _replace_check("agent_runs", _AGENT_STATUS_CONSTRAINT, _NEW_AGENT_STATUS)
    with op.batch_alter_table("workflow_jobs") as batch_op:
        batch_op.add_column(sa.Column("resume_payload_json", sa.JSON(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    waiting_approval = bind.execute(
        sa.text("SELECT COUNT(*) FROM content_projects WHERE status = 'waiting_approval'")
    ).scalar_one()
    cancelled_runs = bind.execute(
        sa.text("SELECT COUNT(*) FROM agent_runs WHERE status = 'cancelled'")
    ).scalar_one()
    resume_payloads = bind.execute(
        sa.text("SELECT COUNT(*) FROM workflow_jobs WHERE resume_payload_json IS NOT NULL")
    ).scalar_one()
    if waiting_approval or cancelled_runs or resume_payloads:
        raise RuntimeError("phase_d_downgrade_blocked: approval/cancellation data still exists")

    with op.batch_alter_table("workflow_jobs") as batch_op:
        batch_op.drop_column("resume_payload_json")
    _replace_check("agent_runs", _AGENT_STATUS_CONSTRAINT, _OLD_AGENT_STATUS)
    _replace_check("content_projects", _PROJECT_STATUS_CONSTRAINT, _OLD_PROJECT_STATUS)
