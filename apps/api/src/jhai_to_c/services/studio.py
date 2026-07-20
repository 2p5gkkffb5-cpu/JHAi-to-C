from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from jhai_to_c.contracts.studio import StudioResourceCreate, StudioResourceUpdate
from jhai_to_c.db.models import StudioResource, StudioResourceRevision


class StudioResourceNotFoundError(LookupError):
    pass


class StudioRevisionConflictError(RuntimeError):
    def __init__(self, current_revision: int) -> None:
        self.current_revision = current_revision
        super().__init__(f"Studio resource is already at revision {current_revision}")


class StudioService:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def create(self, module: str, data: StudioResourceCreate) -> StudioResource:
        resource = StudioResource(
            module=module,
            title=data.title,
            content=data.content,
            status=data.status,
            revision=1,
            created_by=data.actor,
            updated_by=data.actor,
        )
        async with self._session_factory.begin() as session:
            session.add(resource)
            await session.flush()
            session.add(self._snapshot(resource, actor=data.actor, change_note="created"))
            await session.flush()
        return resource

    async def list(
        self, module: str, *, status: str | None = None
    ) -> list[StudioResource]:
        statement = select(StudioResource).where(StudioResource.module == module)
        if status is not None:
            statement = statement.where(StudioResource.status == status)
        statement = statement.order_by(StudioResource.updated_at.desc(), StudioResource.id)
        async with self._session_factory() as session:
            return list((await session.scalars(statement)).all())

    async def get(self, module: str, resource_id: str) -> StudioResource:
        async with self._session_factory() as session:
            resource = await session.get(StudioResource, resource_id)
            if resource is None or resource.module != module:
                raise StudioResourceNotFoundError(resource_id)
            return resource

    async def update(
        self, module: str, resource_id: str, data: StudioResourceUpdate
    ) -> StudioResource:
        async with self._session_factory.begin() as session:
            resource = await session.get(StudioResource, resource_id)
            if resource is None or resource.module != module:
                raise StudioResourceNotFoundError(resource_id)
            if resource.revision != data.expected_revision:
                raise StudioRevisionConflictError(resource.revision)

            if "title" in data.model_fields_set:
                resource.title = data.title  # type: ignore[assignment]
            if "content" in data.model_fields_set:
                resource.content = data.content  # type: ignore[assignment]
            if "status" in data.model_fields_set:
                resource.status = data.status  # type: ignore[assignment]
            resource.revision += 1
            resource.updated_by = data.actor
            session.add(
                self._snapshot(resource, actor=data.actor, change_note=data.change_note)
            )
            await session.flush()
        return resource

    async def duplicate(
        self, module: str, resource_id: str, *, title: str | None, actor: str
    ) -> StudioResource:
        source = await self.get(module, resource_id)
        return await self.create(
            module,
            StudioResourceCreate(
                title=title or f"{source.title} 副本",
                content=dict(source.content),
                status="draft",
                actor=actor,
            ),
        )

    async def revisions(
        self, module: str, resource_id: str
    ) -> list[StudioResourceRevision]:
        await self.get(module, resource_id)
        statement = (
            select(StudioResourceRevision)
            .where(StudioResourceRevision.resource_id == resource_id)
            .order_by(StudioResourceRevision.revision.desc())
        )
        async with self._session_factory() as session:
            return list((await session.scalars(statement)).all())

    @staticmethod
    def _snapshot(
        resource: StudioResource, *, actor: str, change_note: str | None
    ) -> StudioResourceRevision:
        return StudioResourceRevision(
            resource_id=resource.id,
            revision=resource.revision,
            title=resource.title,
            content=dict(resource.content),
            status=resource.status,
            actor=actor,
            change_note=change_note,
        )
