import sqlite3

import pytest
from alembic import command
from alembic.config import Config


def _config() -> Config:
    return Config("alembic.ini")


def test_0010_marks_ambiguous_history_legacy_and_defaults_new_projects_to_agent(
    tmp_path, monkeypatch
) -> None:
    database_path = tmp_path / "content-project-origin-migration.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{database_path}")
    command.upgrade(_config(), "20260720_0009")

    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "INSERT INTO content_projects (id, title, request_text) VALUES (?, ?, ?)",
            ("legacy-project", "历史项目", "来源在旧版本中不可判定"),
        )
        connection.commit()

    command.upgrade(_config(), "20260720_0010")

    with sqlite3.connect(database_path) as connection:
        assert connection.execute(
            "SELECT origin FROM content_projects WHERE id='legacy-project'"
        ).fetchone()[0] == "legacy"

        connection.execute(
            "INSERT INTO content_projects (id, title, request_text) VALUES (?, ?, ?)",
            ("new-project", "新项目", "新记录使用明确的默认来源"),
        )
        assert connection.execute(
            "SELECT origin FROM content_projects WHERE id='new-project'"
        ).fetchone()[0] == "agent"

        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE content_projects SET origin='unknown' WHERE id='new-project'"
            )


def test_0011_downgrade_maps_video_clone_history_to_ai_video(tmp_path, monkeypatch) -> None:
    database_path = tmp_path / "video-clone-origin-migration.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{database_path}")
    command.upgrade(_config(), "20260720_0011")

    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            INSERT INTO content_projects (id, title, request_text, origin)
            VALUES (?, ?, ?, ?)
            """,
            ("clone-project", "复刻项目", "复刻一条参考视频", "video_clone"),
        )
        connection.commit()

    command.downgrade(_config(), "20260720_0010")

    with sqlite3.connect(database_path) as connection:
        assert connection.execute(
            "SELECT origin FROM content_projects WHERE id='clone-project'"
        ).fetchone()[0] == "ai_video"
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE content_projects SET origin='video_clone' WHERE id='clone-project'"
            )
