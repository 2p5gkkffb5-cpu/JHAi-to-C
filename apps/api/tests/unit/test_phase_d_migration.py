import json
import sqlite3

import pytest
from alembic import command
from alembic.config import Config


def _config() -> Config:
    return Config("alembic.ini")


def _insert_project(connection: sqlite3.Connection, project_id: str) -> None:
    connection.execute(
        "INSERT INTO content_projects (id, title, request_text) VALUES (?, ?, ?)",
        (project_id, "Phase D migration", "verify approval and cancellation storage"),
    )


def test_0003_adds_approval_cancel_and_resume_payload_storage(tmp_path, monkeypatch) -> None:
    database_path = tmp_path / "phase-d-migration.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{database_path}")
    command.upgrade(_config(), "20260716_0002")

    with sqlite3.connect(database_path) as connection:
        _insert_project(connection, "project-phase-d")
        connection.execute(
            """
            INSERT INTO agent_runs
              (id, project_id, agent_name, node_name, status)
            VALUES ('legacy-run', 'project-phase-d', 'research', 'research', 'completed')
            """
        )
        connection.execute(
            """
            INSERT INTO workflow_jobs
              (id, project_id, job_type, status)
            VALUES ('legacy-job', 'project-phase-d', 'run_project', 'completed')
            """
        )
        connection.commit()

    command.upgrade(_config(), "20260716_0003")

    resume_payload = {
        "node_name": "strategy",
        "action": "approve",
        "strategy_id": "strategy-scene",
    }
    with sqlite3.connect(database_path) as connection:
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone()[0] == (
            "20260716_0003"
        )
        workflow_job_columns = {
            row[1] for row in connection.execute("PRAGMA table_info('workflow_jobs')").fetchall()
        }
        assert "resume_payload_json" in workflow_job_columns

        connection.execute(
            "UPDATE content_projects SET status='waiting_approval' WHERE id='project-phase-d'"
        )
        connection.execute(
            """
            INSERT INTO agent_runs
              (id, project_id, agent_name, node_name, status)
            VALUES ('cancelled-run', 'project-phase-d', 'strategy', 'strategy', 'cancelled')
            """
        )
        connection.execute(
            """
            UPDATE workflow_jobs
            SET resume_payload_json=?
            WHERE id='legacy-job'
            """,
            (json.dumps(resume_payload),),
        )
        connection.commit()

        assert (
            connection.execute(
                "SELECT status FROM content_projects WHERE id='project-phase-d'"
            ).fetchone()[0]
            == "waiting_approval"
        )
        assert (
            connection.execute("SELECT status FROM agent_runs WHERE id='cancelled-run'").fetchone()[
                0
            ]
            == "cancelled"
        )
        stored_payload = connection.execute(
            "SELECT resume_payload_json FROM workflow_jobs WHERE id='legacy-job'"
        ).fetchone()[0]
        assert json.loads(stored_payload) == resume_payload
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []

        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE content_projects SET status='waiting_unknown' WHERE id='project-phase-d'"
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO agent_runs
                  (id, project_id, agent_name, node_name, status)
                VALUES (
                  'invalid-run', 'project-phase-d', 'strategy', 'strategy', 'interrupted'
                )
                """
            )


def test_0003_downgrade_refuses_to_discard_phase_d_data(tmp_path, monkeypatch) -> None:
    database_path = tmp_path / "phase-d-downgrade.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{database_path}")
    command.upgrade(_config(), "20260716_0003")

    with sqlite3.connect(database_path) as connection:
        _insert_project(connection, "project-downgrade")
        connection.execute(
            "UPDATE content_projects SET status='waiting_approval' WHERE id='project-downgrade'"
        )
        connection.commit()

    with pytest.raises(RuntimeError, match="phase_d_downgrade_blocked"):
        command.downgrade(_config(), "20260716_0002")

    with sqlite3.connect(database_path) as connection:
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone()[0] == (
            "20260716_0003"
        )
