import sqlite3

import pytest
from alembic import command
from alembic.config import Config


def _config() -> Config:
    return Config("alembic.ini")


def _insert_project(connection: sqlite3.Connection, project_id: str) -> None:
    connection.execute(
        "INSERT INTO content_projects (id, title, request_text) VALUES (?, ?, ?)",
        (project_id, "migration", "migration test"),
    )


def test_real_0001_to_0002_chain_and_safe_downgrade(tmp_path, monkeypatch) -> None:
    database_path = tmp_path / "migration.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{database_path}")
    command.upgrade(_config(), "20260716_0001")
    with sqlite3.connect(database_path) as connection:
        _insert_project(connection, "project-1")
        connection.execute(
            """
            INSERT INTO agent_runs
              (id, project_id, agent_name, node_name, status)
            VALUES ('legacy', 'project-1', 'production', 'copywriting', 'completed')
            """
        )
        connection.commit()

    command.upgrade(_config(), "head")
    with sqlite3.connect(database_path) as connection:
        table_sql = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='agent_runs'"
        ).fetchone()[0]
        assert "ck_agent_runs_ck_agent_runs_agent_name" in table_sql
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM agent_runs WHERE agent_name='production'"
            ).fetchone()[0]
            == 1
        )
        for index, identity in enumerate(
            (
                "production_coordinator",
                "copywriter_agent",
                "storyboard_agent",
                "video_prompt_agent",
            )
        ):
            connection.execute(
                """
                INSERT INTO agent_runs
                  (id, project_id, agent_name, node_name, status)
                VALUES (?, 'project-1', ?, ?, 'completed')
                """,
                (f"new-{index}", identity, identity),
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO agent_runs
                  (id, project_id, agent_name, node_name, status)
                VALUES ('unknown', 'project-1', 'unknown', 'unknown', 'completed')
                """
            )
        connection.commit()

    with pytest.raises(RuntimeError, match="phase_c_downgrade_blocked"):
        command.downgrade(_config(), "20260716_0001")
    with sqlite3.connect(database_path) as connection:
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone()[0] == (
            "20260716_0002"
        )
        connection.execute("DELETE FROM agent_runs WHERE id LIKE 'new-%'")
        connection.commit()

    command.downgrade(_config(), "20260716_0001")
    command.upgrade(_config(), "head")
    with sqlite3.connect(database_path) as connection:
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        indexes = {
            row[1] for row in connection.execute("PRAGMA index_list('agent_runs')").fetchall()
        }
        assert "idx_agent_runs_project_created" in indexes


@pytest.mark.parametrize(
    ("job_statuses", "running_agent_run", "orphan_project"),
    [
        (("pending",), False, False),
        (("running",), False, False),
        (("pending", "running"), False, False),
        ((), True, False),
        ((), False, True),
    ],
)
def test_0002_rejects_nonzero_deployment_gate(
    tmp_path,
    monkeypatch,
    job_statuses,
    running_agent_run,
    orphan_project,
) -> None:
    database_path = tmp_path / "migration-gate.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{database_path}")
    command.upgrade(_config(), "20260716_0001")
    with sqlite3.connect(database_path) as connection:
        _insert_project(connection, "project-gate")
        for index, status in enumerate(job_statuses):
            connection.execute(
                """
                INSERT INTO workflow_jobs (id, project_id, status)
                VALUES (?, 'project-gate', ?)
                """,
                (f"job-gate-{index}", status),
            )
        if running_agent_run:
            connection.execute(
                """
                INSERT INTO agent_runs
                  (id, project_id, agent_name, node_name, status)
                VALUES ('run-gate', 'project-gate', 'director', 'director', 'running')
                """
            )
        if orphan_project:
            connection.execute(
                "UPDATE content_projects SET status='running' WHERE id='project-gate'"
            )
        connection.commit()

    with pytest.raises(RuntimeError, match="phase_c_deployment_gate_failed"):
        command.upgrade(_config(), "head")
    with sqlite3.connect(database_path) as connection:
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone()[0] == (
            "20260716_0001"
        )
