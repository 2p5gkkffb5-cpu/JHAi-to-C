from __future__ import annotations

from pathlib import Path

from sqlalchemy import event
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from .base import Base


def _ensure_sqlite_parent(database_url: str) -> None:
    url = make_url(database_url)
    if url.get_backend_name() != "sqlite" or not url.database or url.database == ":memory:":
        return
    Path(url.database).expanduser().parent.mkdir(parents=True, exist_ok=True)


def create_database_engine(database_url: str, *, echo: bool = False) -> AsyncEngine:
    """Build the Phase 1 async engine and enable SQLite foreign keys."""

    _ensure_sqlite_parent(database_url)
    engine = create_async_engine(database_url, echo=echo)

    if make_url(database_url).get_backend_name() == "sqlite":

        @event.listens_for(engine.sync_engine, "connect")
        def _enable_sqlite_foreign_keys(dbapi_connection: object, _: object) -> None:
            cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


def create_session_factory(
    engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def create_schema(engine: AsyncEngine) -> None:
    """Create tables for isolated tests; runtime databases should use Alembic."""

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


class Database:
    """Small lifecycle wrapper used by FastAPI and the in-process runner."""

    def __init__(self, database_url: str, *, echo: bool = False) -> None:
        self.engine = create_database_engine(database_url, echo=echo)
        self.session_factory = create_session_factory(self.engine)

    async def create_schema(self) -> None:
        await create_schema(self.engine)

    async def dispose(self) -> None:
        await self.engine.dispose()
