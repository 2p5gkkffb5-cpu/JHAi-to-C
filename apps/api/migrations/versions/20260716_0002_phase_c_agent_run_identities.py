"""Expand AgentRun identities for the Phase C Production team.

Revision ID: 20260716_0002
Revises: 20260716_0001
Create Date: 2026-07-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260716_0002"
down_revision: str | None = "20260716_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PHYSICAL_CONSTRAINT_NAME = "ck_agent_runs_ck_agent_runs_agent_name"
_LEGACY_EXPRESSION = (
    "agent_name IN ('director', 'research', 'strategy', 'production', 'reviewer')"
)
_PHASE_C_EXPRESSION = (
    "agent_name IN ('director', 'research', 'strategy', 'production', "
    "'production_coordinator', 'copywriter_agent', 'storyboard_agent', "
    "'video_prompt_agent', 'reviewer')"
)
_NEW_IDENTITIES = (
    "production_coordinator",
    "copywriter_agent",
    "storyboard_agent",
    "video_prompt_agent",
)


def _scalar(bind: sa.Connection, sql: str, parameters: dict[str, object] | None = None) -> int:
    return int(bind.execute(sa.text(sql), parameters or {}).scalar_one())


def _assert_deployment_gate(bind: sa.Connection) -> None:
    pending_count, running_count = bind.execute(
        sa.text(
            """
            SELECT
              COALESCE(SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END), 0),
              COALESCE(SUM(CASE WHEN status = 'running' THEN 1 ELSE 0 END), 0)
            FROM workflow_jobs
            WHERE status IN ('pending', 'running')
            """
        )
    ).one()
    running_agent_runs = _scalar(
        bind,
        "SELECT COUNT(*) FROM agent_runs WHERE status = 'running'",
    )
    orphan_projects = _scalar(
        bind,
        """
        SELECT COUNT(*)
        FROM content_projects AS project
        WHERE project.status IN ('running', 'reviewing', 'generating')
          AND NOT EXISTS (
            SELECT 1
            FROM workflow_jobs AS job
            WHERE job.project_id = project.id
              AND job.status IN ('pending', 'running')
          )
        """,
    )
    if pending_count or running_count or running_agent_runs or orphan_projects:
        raise RuntimeError(
            "phase_c_deployment_gate_failed: "
            f"pending={pending_count}, running={running_count}, "
            f"running_agent_runs={running_agent_runs}, orphan_projects={orphan_projects}"
        )


def _assert_revision(bind: sa.Connection, expected: str) -> None:
    current = bind.execute(sa.text("SELECT version_num FROM alembic_version")).scalar_one()
    if current != expected:
        raise RuntimeError(f"expected database revision {expected}, found {current}")


def _assert_integrity(bind: sa.Connection) -> None:
    violations = list(bind.execute(sa.text("PRAGMA foreign_key_check")))
    if violations:
        raise RuntimeError(f"foreign_key_check failed: {violations}")


def _replace_constraint(expression: str) -> None:
    final_name = op.f(_PHYSICAL_CONSTRAINT_NAME)
    with op.batch_alter_table("agent_runs") as batch_op:
        batch_op.drop_constraint(final_name, type_="check")
        batch_op.create_check_constraint(final_name, expression)


def upgrade() -> None:
    bind = op.get_bind()
    _assert_revision(bind, "20260716_0001")
    _assert_deployment_gate(bind)
    row_count = _scalar(bind, "SELECT COUNT(*) FROM agent_runs")
    legacy_count = _scalar(
        bind,
        "SELECT COUNT(*) FROM agent_runs WHERE agent_name = 'production'",
    )
    _replace_constraint(_PHASE_C_EXPRESSION)
    if _scalar(bind, "SELECT COUNT(*) FROM agent_runs") != row_count:
        raise RuntimeError("agent_runs row count changed during Phase C upgrade")
    if (
        _scalar(bind, "SELECT COUNT(*) FROM agent_runs WHERE agent_name = 'production'")
        != legacy_count
    ):
        raise RuntimeError("legacy production AgentRun count changed during Phase C upgrade")
    _assert_integrity(bind)


def downgrade() -> None:
    bind = op.get_bind()
    _assert_revision(bind, "20260716_0002")
    _assert_deployment_gate(bind)
    placeholders = ", ".join(f":identity_{index}" for index in range(len(_NEW_IDENTITIES)))
    parameters = {
        f"identity_{index}": identity for index, identity in enumerate(_NEW_IDENTITIES)
    }
    new_identity_count = _scalar(
        bind,
        f"SELECT COUNT(*) FROM agent_runs WHERE agent_name IN ({placeholders})",
        parameters,
    )
    if new_identity_count:
        raise RuntimeError(
            "phase_c_downgrade_blocked: new Production AgentRun identities still exist"
        )
    row_count = _scalar(bind, "SELECT COUNT(*) FROM agent_runs")
    _replace_constraint(_LEGACY_EXPRESSION)
    if _scalar(bind, "SELECT COUNT(*) FROM agent_runs") != row_count:
        raise RuntimeError("agent_runs row count changed during Phase C downgrade")
    _assert_integrity(bind)
