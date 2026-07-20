from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from enum import Enum
from typing import Any, Final, cast

from pydantic import BaseModel, TypeAdapter
from sqlalchemy import case, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from jhai_to_c.contracts.project import AgentDecisionRequest, ContentProjectCreate
from jhai_to_c.contracts.strategy import StrategyOutput
from jhai_to_c.db.base import utc_now
from jhai_to_c.db.models import (
    AgentRun,
    Artifact,
    ContentProject,
    ProjectEvent,
    ProjectReference,
    VideoTask,
    WorkflowJob,
)

JsonObject = dict[str, Any]
_UNSET: Final = object()
_JSON_ADAPTER = TypeAdapter(Any)


class PersistenceEntityNotFoundError(LookupError):
    def __init__(self, entity: str, entity_id: str) -> None:
        self.entity = entity
        self.entity_id = entity_id
        super().__init__(f"{entity} not found: {entity_id}")


class ProjectNotFoundError(PersistenceEntityNotFoundError):
    def __init__(self, project_id: str) -> None:
        super().__init__("ContentProject", project_id)


class ProjectStartConflictError(RuntimeError):
    def __init__(self, project_id: str, current_status: str) -> None:
        self.project_id = project_id
        self.current_status = current_status
        super().__init__(f"ContentProject {project_id} cannot start from status '{current_status}'")


class InvalidStrategySelectionError(ValueError):
    def __init__(self, strategy_id: str) -> None:
        self.strategy_id = strategy_id
        super().__init__(f"Strategy does not belong to this project: {strategy_id}")


class DeploymentCutoverConflictError(RuntimeError):
    pass


def _enum_value(value: str | Enum) -> str:
    return str(value.value if isinstance(value, Enum) else value)


def _json_object(value: BaseModel | Mapping[str, Any]) -> JsonObject:
    encoded = _JSON_ADAPTER.dump_python(value, mode="json")
    if not isinstance(encoded, dict):
        raise TypeError("Persistence JSON payload must be an object")
    return cast(JsonObject, encoded)


class ContentProjectService:
    """Transaction boundary for project, workflow, artifact, and event persistence."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def create_project(
        self,
        data: ContentProjectCreate | Mapping[str, Any] | None = None,
        **values: Any,
    ) -> ContentProject:
        payload: JsonObject
        if data is None:
            payload = _json_object(values)
        elif values:
            payload = _json_object(data)
            payload.update(_json_object(values))
        else:
            payload = _json_object(data)

        references = payload.pop("references", [])
        project = ContentProject(
            owner_id=payload.get("owner_id"),
            title=payload["title"],
            request_text=payload["request_text"],
            target_platform=payload.get("target_platform", "douyin"),
            duration_seconds=payload.get("duration_seconds", 20),
            aspect_ratio=payload.get("aspect_ratio", "9:16"),
            blueprint_id=payload.get("blueprint_id"),
            requested_mode=payload.get("requested_mode", "full_creation"),
            origin=payload.get("origin", "agent"),
        )
        project.references = [
            ProjectReference(
                reference_type=reference["type"],
                reference_id=reference["id"],
                label=reference["label"],
                snapshot=reference.get("snapshot", {}),
                position=position,
            )
            for position, reference in enumerate(references)
        ]

        async with self._session_factory.begin() as session:
            session.add(project)
            await session.flush()
        return project

    async def get_project(self, project_id: str) -> ContentProject | None:
        statement = (
            select(ContentProject)
            .where(ContentProject.id == project_id)
            .options(
                selectinload(ContentProject.references),
                selectinload(ContentProject.artifacts),
                selectinload(ContentProject.video_tasks),
            )
        )
        async with self._session_factory() as session:
            return (await session.execute(statement)).scalar_one_or_none()

    async def list_projects(
        self,
        *,
        limit: int = 50,
        owner_id: str | None = None,
        origin: str | None = None,
    ) -> list[ContentProject]:
        statement = (
            select(ContentProject)
            .order_by(ContentProject.updated_at.desc(), ContentProject.id.desc())
            .limit(limit)
        )
        if owner_id is not None:
            statement = statement.where(ContentProject.owner_id == owner_id)
        if origin is not None:
            statement = statement.where(ContentProject.origin == origin)
        async with self._session_factory() as session:
            return list((await session.scalars(statement)).all())

    async def update_status(
        self,
        project_id: str,
        status: str | Enum,
        *,
        current_node: str | None | object = _UNSET,
        selected_strategy_id: str | None | object = _UNSET,
        resolved_intent: str | Enum | None | object = _UNSET,
        final_result: BaseModel | Mapping[str, Any] | None | object = _UNSET,
        error: BaseModel | Mapping[str, Any] | None | object = _UNSET,
    ) -> ContentProject:
        status_value = _enum_value(status)
        now = utc_now()
        async with self._session_factory.begin() as session:
            project = await session.get(ContentProject, project_id)
            if project is None:
                raise ProjectNotFoundError(project_id)
            if project.status == "cancelled" and status_value != "cancelled":
                return project
            project.status = status_value
            if current_node is not _UNSET:
                project.current_node = cast(str | None, current_node)
            if selected_strategy_id is not _UNSET:
                project.selected_strategy_id = cast(str | None, selected_strategy_id)
            if resolved_intent is not _UNSET:
                project.resolved_intent = (
                    None
                    if resolved_intent is None
                    else _enum_value(cast(str | Enum, resolved_intent))
                )
            if final_result is not _UNSET:
                project.final_result = (
                    None
                    if final_result is None
                    else _json_object(cast(BaseModel | Mapping[str, Any], final_result))
                )
            if error is not _UNSET:
                project.error = (
                    None
                    if error is None
                    else _json_object(cast(BaseModel | Mapping[str, Any], error))
                )
            if status_value == "running" and project.started_at is None:
                project.started_at = now
            if status_value in {"completed", "failed", "cancelled"}:
                project.completed_at = now
            await session.flush()
        return project

    async def save_artifact(
        self,
        project_id: str,
        artifact_type: str | Enum,
        content: BaseModel | Mapping[str, Any],
        *,
        version: int | None = None,
    ) -> Artifact:
        artifact_type_value = _enum_value(artifact_type)
        async with self._session_factory.begin() as session:
            if version is None:
                version_statement = select(func.coalesce(func.max(Artifact.version), 0) + 1).where(
                    Artifact.project_id == project_id,
                    Artifact.artifact_type == artifact_type_value,
                )
                version = (await session.execute(version_statement)).scalar_one()
            artifact = Artifact(
                project_id=project_id,
                artifact_type=artifact_type_value,
                version=version,
                content=_json_object(content),
            )
            session.add(artifact)
            await session.flush()
        return artifact

    async def start_agent_run(
        self,
        project_id: str,
        *,
        agent_name: str | Enum,
        node_name: str,
        input_data: BaseModel | Mapping[str, Any] | None = None,
        attempt: int | None = None,
    ) -> AgentRun:
        agent_name_value = _enum_value(agent_name)
        async with self._session_factory.begin() as session:
            if attempt is None:
                attempt_statement = select(func.coalesce(func.max(AgentRun.attempt), 0) + 1).where(
                    AgentRun.project_id == project_id,
                    AgentRun.node_name == node_name,
                )
                attempt = (await session.execute(attempt_statement)).scalar_one()
            agent_run = AgentRun(
                project_id=project_id,
                agent_name=agent_name_value,
                node_name=node_name,
                status="running",
                attempt=attempt,
                input_data=None if input_data is None else _json_object(input_data),
                started_at=utc_now(),
            )
            session.add(agent_run)
            await session.flush()
        return agent_run

    async def finish_agent_run(
        self,
        run_id: str,
        *,
        status: str | Enum = "completed",
        output_data: BaseModel | Mapping[str, Any] | None = None,
        error: BaseModel | Mapping[str, Any] | None = None,
    ) -> AgentRun:
        async with self._session_factory.begin() as session:
            agent_run = await session.get(AgentRun, run_id)
            if agent_run is None:
                raise PersistenceEntityNotFoundError("AgentRun", run_id)
            status_value = _enum_value(status)
            if agent_run.status == "cancelled" and status_value != "cancelled":
                return agent_run
            agent_run.status = status_value
            if output_data is not None:
                agent_run.output_data = _json_object(output_data)
            if error is not None:
                agent_run.error = _json_object(error)
            agent_run.completed_at = utc_now()
            await session.flush()
        return agent_run

    async def append_event(
        self,
        project_id: str,
        event_type: str,
        *,
        node_name: str | None = None,
        payload: BaseModel | Mapping[str, Any] | None = None,
    ) -> ProjectEvent:
        event = ProjectEvent(
            project_id=project_id,
            event_type=event_type,
            node_name=node_name,
            payload={} if payload is None else _json_object(payload),
        )
        async with self._session_factory.begin() as session:
            session.add(event)
            await session.flush()
        return event

    async def create_or_update_video_task(
        self,
        project_id: str,
        *,
        provider: str,
        is_mock: bool,
        status: str | Enum,
        request_data: BaseModel | Mapping[str, Any] | None = None,
        external_task_id: str | None = None,
        task_id: str | None = None,
        progress: float | None | object = _UNSET,
        result_url: str | None | object = _UNSET,
        error: BaseModel | Mapping[str, Any] | None | object = _UNSET,
    ) -> VideoTask:
        async with self._session_factory.begin() as session:
            video_task: VideoTask | None = None
            if task_id is not None:
                video_task = await session.get(VideoTask, task_id)
                if video_task is not None and video_task.project_id != project_id:
                    raise PersistenceEntityNotFoundError("VideoTask", task_id)
            elif external_task_id is not None:
                statement = select(VideoTask).where(
                    VideoTask.project_id == project_id,
                    VideoTask.provider == provider,
                    VideoTask.external_task_id == external_task_id,
                )
                video_task = (await session.execute(statement)).scalar_one_or_none()
            else:
                statement = (
                    select(VideoTask)
                    .where(VideoTask.project_id == project_id, VideoTask.provider == provider)
                    .order_by(VideoTask.created_at.desc(), VideoTask.id.desc())
                    .limit(1)
                )
                video_task = (await session.execute(statement)).scalar_one_or_none()

            if video_task is None:
                video_task = VideoTask(
                    project_id=project_id,
                    provider=provider,
                    is_mock=is_mock,
                    external_task_id=external_task_id,
                    status=_enum_value(status),
                    request_data={} if request_data is None else _json_object(request_data),
                    progress=None if progress is _UNSET else cast(float | None, progress),
                    result_url=None if result_url is _UNSET else cast(str | None, result_url),
                    error=(
                        None
                        if error is _UNSET or error is None
                        else _json_object(cast(BaseModel | Mapping[str, Any], error))
                    ),
                )
                session.add(video_task)
            else:
                video_task.provider = provider
                video_task.is_mock = is_mock
                video_task.status = _enum_value(status)
                if external_task_id is not None:
                    video_task.external_task_id = external_task_id
                if request_data is not None:
                    video_task.request_data = _json_object(request_data)
                if progress is not _UNSET:
                    video_task.progress = cast(float | None, progress)
                if result_url is not _UNSET:
                    video_task.result_url = cast(str | None, result_url)
                if error is not _UNSET:
                    video_task.error = (
                        None
                        if error is None
                        else _json_object(cast(BaseModel | Mapping[str, Any], error))
                    )
            await session.flush()
        return video_task

    async def create_job(
        self,
        project_id: str,
        *,
        job_type: str | Enum = "run_project",
        available_at: datetime | None = None,
    ) -> WorkflowJob:
        job_type_value = _enum_value(job_type)
        if job_type_value == "resume_project":
            raise ValueError("same_thread_resume_not_supported")
        job = WorkflowJob(
            project_id=project_id,
            job_type=job_type_value,
            status="pending",
            available_at=available_at or utc_now(),
        )
        async with self._session_factory.begin() as session:
            session.add(job)
            await session.flush()
        return job

    async def create_start_job(
        self,
        project_id: str,
        *,
        provider: str = "mock",
    ) -> WorkflowJob:
        """Atomically claim a draft project and create its first workflow job."""

        now = utc_now()
        transition = (
            update(ContentProject)
            .where(
                ContentProject.id == project_id,
                ContentProject.status == "draft",
            )
            .values(
                status="running",
                current_node=None,
                error=None,
                started_at=now,
                updated_at=now,
            )
        )
        async with self._session_factory.begin() as session:
            result = await session.execute(transition)
            if result.rowcount != 1:  # type: ignore[attr-defined]
                current_status = await session.scalar(
                    select(ContentProject.status).where(ContentProject.id == project_id)
                )
                if current_status is None:
                    raise ProjectNotFoundError(project_id)
                raise ProjectStartConflictError(project_id, current_status)

            job = WorkflowJob(
                project_id=project_id,
                job_type="run_project",
                status="pending",
                available_at=now,
            )
            session.add(job)
            await session.flush()
            session.add(
                ProjectEvent(
                    project_id=project_id,
                    event_type="workflow.queued",
                    payload={"job_id": job.id, "provider": provider},
                )
            )
            await session.flush()
        return job

    async def create_strategy_resume_job(
        self,
        project_id: str,
        *,
        strategy_id: str,
        provider: str = "mock",
    ) -> WorkflowJob:
        """Compatibility wrapper for the original strategy-selection endpoint."""

        return await self.create_agent_decision_resume_job(
            project_id,
            AgentDecisionRequest(
                node_name="research",
                action="approve",
                strategy_id=strategy_id,
            ),
            provider=provider,
        )

    async def create_agent_decision_resume_job(
        self,
        project_id: str,
        decision: AgentDecisionRequest | Mapping[str, Any],
        *,
        provider: str = "mock",
    ) -> WorkflowJob:
        """Validate one outstanding Agent gate and atomically queue its resume."""

        data = AgentDecisionRequest.model_validate(decision)
        now = utc_now()
        resume_payload = data.model_dump(mode="json", exclude_none=True)
        async with self._session_factory.begin() as session:
            project = await session.get(ContentProject, project_id)
            if project is None:
                raise ProjectNotFoundError(project_id)
            valid_status = project.status == "waiting_approval" or (
                project.status == "waiting_strategy" and data.node_name == "research"
            )
            if not valid_status or project.current_node != data.node_name:
                raise ProjectStartConflictError(project_id, project.status)

            if data.node_name == "research" and data.action == "approve":
                artifact = await session.scalar(
                    select(Artifact)
                    .where(
                        Artifact.project_id == project_id,
                        Artifact.artifact_type == "strategy",
                    )
                    .order_by(Artifact.version.desc())
                    .limit(1)
                )
                if artifact is None:
                    raise InvalidStrategySelectionError(data.strategy_id or "")
                strategies = StrategyOutput.model_validate(artifact.content)
                allowed_ids = {option.strategy_id for option in strategies.strategy_options}
                if data.strategy_id not in allowed_ids:
                    raise InvalidStrategySelectionError(data.strategy_id or "")

            allowed_statuses = ("waiting_approval", "waiting_strategy") if (
                data.node_name == "research"
            ) else ("waiting_approval",)
            project_values: dict[str, Any] = {
                "status": "running",
                "current_node": data.node_name,
                "error": None,
                "completed_at": None,
                "updated_at": now,
            }
            if data.node_name == "research":
                project_values["selected_strategy_id"] = (
                    data.strategy_id if data.action == "approve" else None
                )
            claim = await session.execute(
                update(ContentProject)
                .where(
                    ContentProject.id == project_id,
                    ContentProject.status.in_(allowed_statuses),
                    ContentProject.current_node == data.node_name,
                )
                .values(**project_values)
                .execution_options(synchronize_session=False)
            )
            if claim.rowcount != 1:  # type: ignore[attr-defined]
                current_status = await session.scalar(
                    select(ContentProject.status).where(ContentProject.id == project_id)
                )
                raise ProjectStartConflictError(
                    project_id,
                    str(current_status or project.status),
                )

            job = WorkflowJob(
                project_id=project_id,
                job_type="resume_project",
                status="pending",
                available_at=now,
                resume_payload=resume_payload,
            )
            session.add(job)
            await session.flush()

            event_payload = {
                "job_id": job.id,
                "action": data.action,
                "feedback": data.feedback,
                "strategy_id": data.strategy_id,
            }
            events = [
                ProjectEvent(
                    project_id=project_id,
                    event_type="agent.decision_submitted",
                    node_name=data.node_name,
                    payload=event_payload,
                )
            ]
            if data.action == "retry":
                events.append(
                    ProjectEvent(
                        project_id=project_id,
                        event_type="agent.retry_queued",
                        node_name=data.node_name,
                        payload=event_payload,
                    )
                )
            elif data.node_name == "research":
                events.append(
                    ProjectEvent(
                        project_id=project_id,
                        event_type="strategy.selected",
                        node_name="research",
                        payload={"strategy_id": data.strategy_id},
                    )
                )
            events.append(
                ProjectEvent(
                    project_id=project_id,
                    event_type="workflow.queued",
                    payload={
                        "job_id": job.id,
                        "job_type": "resume_project",
                        "provider": provider,
                        "node_name": data.node_name,
                        "action": data.action,
                    },
                )
            )
            session.add_all(events)
            await session.flush()
        return job

    async def cancel_project(self, project_id: str) -> ContentProject:
        """Atomically terminalize one project and all of its local active work."""

        now = utc_now()
        async with self._session_factory.begin() as session:
            project = await session.get(ContentProject, project_id)
            if project is None:
                raise ProjectNotFoundError(project_id)
            if project.status == "cancelled":
                return project
            if project.status in {"completed", "failed"}:
                raise ProjectStartConflictError(project_id, project.status)

            previous_status = project.status
            project.status = "cancelled"
            project.completed_at = now
            project.error = None
            project.updated_at = now
            await session.execute(
                update(WorkflowJob)
                .where(
                    WorkflowJob.project_id == project_id,
                    WorkflowJob.status.in_(("pending", "running")),
                )
                .values(status="cancelled", last_error="cancelled_by_user", updated_at=now)
            )
            await session.execute(
                update(AgentRun)
                .where(
                    AgentRun.project_id == project_id,
                    AgentRun.status == "running",
                )
                .values(status="cancelled", completed_at=now)
            )
            await session.execute(
                update(VideoTask)
                .where(
                    VideoTask.project_id == project_id,
                    VideoTask.status.in_(("queued", "processing")),
                )
                .values(
                    status="cancelled",
                    error={
                        "code": "cancelled_by_user",
                        "message": "Local tracking stopped after the user cancelled the project",
                    },
                    updated_at=now,
                )
            )
            session.add(
                ProjectEvent(
                    project_id=project_id,
                    event_type="workflow.cancelled",
                    node_name=project.current_node,
                    payload={
                        "previous_status": previous_status,
                        "current_node": project.current_node,
                    },
                )
            )
            await session.flush()
        return project

    async def claim_job(self, job_id: str) -> WorkflowJob | None:
        """Atomically transition one available pending job to running."""

        now = utc_now()
        statement = (
            update(WorkflowJob)
            .where(
                WorkflowJob.id == job_id,
                WorkflowJob.status == "pending",
                WorkflowJob.available_at <= now,
            )
            .values(
                status="running",
                locked_at=now,
                attempts=WorkflowJob.attempts + 1,
            )
        )
        async with self._session_factory.begin() as session:
            result = await session.execute(statement)
            if result.rowcount != 1:  # type: ignore[attr-defined]
                return None
            return await session.get(WorkflowJob, job_id)

    async def finish_job(
        self,
        job_id: str,
        *,
        status: str | Enum,
        last_error: str | None = None,
    ) -> WorkflowJob:
        async with self._session_factory.begin() as session:
            job = await session.get(WorkflowJob, job_id)
            if job is None:
                raise PersistenceEntityNotFoundError("WorkflowJob", job_id)
            status_value = _enum_value(status)
            if job.status == "cancelled" and status_value != "cancelled":
                return job
            job.status = status_value
            job.last_error = last_error
            await session.flush()
        return job

    async def deployment_gate_snapshot(self) -> dict[str, int]:
        """Read all Phase C deployment gates from one database transaction."""

        async with self._session_factory.begin() as session:
            pending_count, running_count = (
                await session.execute(
                    select(
                        func.coalesce(
                            func.sum(case((WorkflowJob.status == "pending", 1), else_=0)),
                            0,
                        ),
                        func.coalesce(
                            func.sum(case((WorkflowJob.status == "running", 1), else_=0)),
                            0,
                        ),
                    ).where(WorkflowJob.status.in_(("pending", "running")))
                )
            ).one()
            running_agent_runs = await session.scalar(
                select(func.count()).select_from(AgentRun).where(AgentRun.status == "running")
            )
            active_job_exists = (
                select(WorkflowJob.id)
                .where(
                    WorkflowJob.project_id == ContentProject.id,
                    WorkflowJob.status.in_(("pending", "running")),
                )
                .exists()
            )
            orphan_projects = await session.scalar(
                select(func.count())
                .select_from(ContentProject)
                .where(
                    ContentProject.status.in_(("running", "reviewing", "generating")),
                    ~active_job_exists,
                )
            )
            concurrent_projects = await session.scalar(
                select(func.count()).select_from(
                    select(WorkflowJob.project_id)
                    .where(WorkflowJob.status.in_(("pending", "running")))
                    .group_by(WorkflowJob.project_id)
                    .having(func.count() > 1)
                    .subquery()
                )
            )
        return {
            "pending_count": int(pending_count),
            "running_count": int(running_count),
            "running_agent_run_count": int(running_agent_runs or 0),
            "orphan_project_count": int(orphan_projects or 0),
            "concurrent_project_count": int(concurrent_projects or 0),
        }

    async def terminalize_deployment_job(self, job_id: str) -> bool:
        """CAS one active job and its project audit chain in one transaction."""

        now = utc_now()
        async with self._session_factory.begin() as session:
            job = await session.get(WorkflowJob, job_id)
            if job is None:
                raise PersistenceEntityNotFoundError("WorkflowJob", job_id)
            if job.status not in {"pending", "running"}:
                return False

            active_job_count = await session.scalar(
                select(func.count())
                .select_from(WorkflowJob)
                .where(
                    WorkflowJob.project_id == job.project_id,
                    WorkflowJob.status.in_(("pending", "running")),
                )
            )
            if active_job_count != 1:
                raise DeploymentCutoverConflictError(
                    f"project {job.project_id} has {active_job_count} active workflow jobs"
                )

            previous_job_status = job.status
            cas = await session.execute(
                update(WorkflowJob)
                .where(
                    WorkflowJob.id == job_id,
                    WorkflowJob.status == previous_job_status,
                )
                .values(status="failed", last_error="deployment_cutover")
            )
            if cas.rowcount != 1:  # type: ignore[attr-defined]
                return False

            project = await session.get(ContentProject, job.project_id)
            if project is None:
                raise ProjectNotFoundError(job.project_id)
            error = {
                "code": "deployment_cutover",
                "message": "Workflow stopped for the Phase C deployment cutover",
                "node": project.current_node,
                "details": {
                    "job_id": job.id,
                    "previous_job_status": previous_job_status,
                },
            }
            await session.execute(
                update(AgentRun)
                .where(
                    AgentRun.project_id == project.id,
                    AgentRun.status == "running",
                )
                .values(status="failed", error=error, completed_at=now)
            )

            if project.status in {"completed", "failed", "cancelled"}:
                job.status = project.status
            else:
                project.status = "failed"
                project.error = error
                project.completed_at = now
                session.add(
                    ProjectEvent(
                        project_id=project.id,
                        event_type="workflow.failed",
                        node_name=None,
                        payload={"job_id": job.id, **error},
                    )
                )
            await session.flush()
        return True

    async def terminalize_orphan_project(self, project_id: str) -> bool:
        """Fail one confirmed execution-state orphan atomically after workers are isolated."""

        now = utc_now()
        async with self._session_factory.begin() as session:
            project_state = (
                await session.execute(
                    select(ContentProject.status, ContentProject.current_node).where(
                        ContentProject.id == project_id
                    )
                )
            ).one_or_none()
            if project_state is None:
                raise ProjectNotFoundError(project_id)
            if project_state.status not in {"running", "reviewing", "generating"}:
                return False
            active_jobs = await session.scalar(
                select(func.count())
                .select_from(WorkflowJob)
                .where(
                    WorkflowJob.project_id == project_id,
                    WorkflowJob.status.in_(("pending", "running")),
                )
            )
            if active_jobs:
                raise DeploymentCutoverConflictError(
                    f"project {project_id} still has {active_jobs} active workflow jobs"
                )
            terminal_job = await session.scalar(
                select(WorkflowJob)
                .where(WorkflowJob.project_id == project_id)
                .order_by(WorkflowJob.updated_at.desc(), WorkflowJob.id.desc())
                .limit(1)
            )
            if terminal_job is None:
                raise DeploymentCutoverConflictError(
                    f"project {project_id} has no terminal workflow job to audit"
                )
            error = {
                "code": "deployment_cutover",
                "message": "Orphan project stopped for the Phase C deployment cutover",
                "node": project_state.current_node,
                "details": {
                    "job_id": terminal_job.id,
                    "previous_job_status": terminal_job.status,
                },
            }
            project_cas = await session.execute(
                update(ContentProject)
                .where(
                    ContentProject.id == project_id,
                    ContentProject.status.in_(("running", "reviewing", "generating")),
                )
                .values(status="failed", error=error, completed_at=now)
            )
            if project_cas.rowcount != 1:  # type: ignore[attr-defined]
                return False

            await session.execute(
                update(AgentRun)
                .where(AgentRun.project_id == project_id, AgentRun.status == "running")
                .values(status="failed", error=error, completed_at=now)
            )
            session.add(
                ProjectEvent(
                    project_id=project_id,
                    event_type="workflow.failed",
                    node_name=None,
                    payload={"job_id": terminal_job.id, **error},
                )
            )
            await session.flush()
        return True

    async def list_events(
        self,
        project_id: str,
        *,
        after_id: int | None = None,
        limit: int = 1000,
    ) -> list[ProjectEvent]:
        statement = select(ProjectEvent).where(ProjectEvent.project_id == project_id)
        if after_id is not None:
            statement = statement.where(ProjectEvent.id > after_id)
        statement = statement.order_by(ProjectEvent.id).limit(limit)
        async with self._session_factory() as session:
            return list((await session.scalars(statement)).all())

    async def list_artifacts(self, project_id: str) -> list[Artifact]:
        statement = (
            select(Artifact)
            .where(Artifact.project_id == project_id)
            .order_by(Artifact.created_at, Artifact.artifact_type, Artifact.version)
        )
        async with self._session_factory() as session:
            return list((await session.scalars(statement)).all())

    async def get_result(self, project_id: str) -> JsonObject:
        async with self._session_factory() as session:
            project = await session.get(ContentProject, project_id)
            if project is None:
                raise ProjectNotFoundError(project_id)

            artifact_statement = (
                select(Artifact)
                .where(Artifact.project_id == project_id)
                .order_by(Artifact.artifact_type, Artifact.version.desc())
            )
            artifacts = list((await session.scalars(artifact_statement)).all())
            latest_artifacts: dict[str, JsonObject] = {}
            for artifact in artifacts:
                latest_artifacts.setdefault(artifact.artifact_type, artifact.content)

            video_statement = (
                select(VideoTask)
                .where(VideoTask.project_id == project_id)
                .order_by(VideoTask.created_at.desc(), VideoTask.id.desc())
                .limit(1)
            )
            video_task = (await session.execute(video_statement)).scalar_one_or_none()

        result = dict(project.final_result or {})
        result.update(
            {
                "project_id": project.id,
                "status": project.status,
                "selected_strategy_id": project.selected_strategy_id,
                "resolved_intent": project.resolved_intent or "full_creation",
                "strategy": latest_artifacts.get("strategy", result.get("strategy", {})),
                "copywriting": latest_artifacts.get("copywriting", result.get("copywriting", {})),
                "storyboard": latest_artifacts.get("storyboard", result.get("storyboard", {})),
                "video_prompt": latest_artifacts.get(
                    "video_prompt", result.get("video_prompt", {})
                ),
                "brand_packaging": latest_artifacts.get(
                    "brand_packaging", result.get("brand_packaging")
                ),
                "review": latest_artifacts.get("review"),
                "video_clone_analysis": latest_artifacts.get(
                    "video_clone_analysis", result.get("video_clone_analysis", {})
                ),
                "video_clone_mapping": latest_artifacts.get(
                    "video_clone_mapping", result.get("video_clone_mapping", {})
                ),
                "video_clone_prompt": latest_artifacts.get(
                    "video_clone_prompt", result.get("video_clone_prompt", {})
                ),
                "video_clone_review": latest_artifacts.get(
                    "video_clone_review", result.get("video_clone_review")
                ),
                "video_task": None if video_task is None else self._video_task_result(video_task),
            }
        )
        return result

    @staticmethod
    def _video_task_result(video_task: VideoTask) -> JsonObject:
        return {
            "task_id": video_task.external_task_id or video_task.id,
            "provider": video_task.provider,
            "is_mock": video_task.is_mock,
            "status": video_task.status,
            "progress": video_task.progress,
            "result_url": video_task.result_url,
            "error_code": None if video_task.error is None else video_task.error.get("code"),
            "error_message": (
                None if video_task.error is None else video_task.error.get("message")
            ),
        }
