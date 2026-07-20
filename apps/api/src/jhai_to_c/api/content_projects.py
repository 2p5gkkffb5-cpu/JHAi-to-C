import asyncio
from collections.abc import AsyncIterator, Mapping
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse

from jhai_to_c.api.auth import AuthGuard
from jhai_to_c.contracts import (
    AgentDecisionRequest,
    ContentProjectCreate,
    ContentProjectRead,
    ContentProjectResult,
    ContentProjectSummary,
    ProjectEventRead,
    SelectStrategyRequest,
    WorkflowCancelResponse,
    WorkflowStartResponse,
)
from jhai_to_c.contracts.project import ProjectOrigin
from jhai_to_c.db.models import ContentProject, VideoTask
from jhai_to_c.runner import WorkflowRunner
from jhai_to_c.services import (
    PERMISSION_CANCEL_PROJECT,
    PERMISSION_CREATE_PROJECT,
    PERMISSION_READ_ALL_PROJECTS,
    PERMISSION_READ_PROJECT,
    PERMISSION_UPDATE_PROJECT,
    AuthPrincipal,
    ContentProjectService,
    InvalidStrategySelectionError,
    ProjectNotFoundError,
    ProjectStartConflictError,
)


def build_content_projects_router(
    service: ContentProjectService,
    runner: WorkflowRunner,
    auth_guard: AuthGuard,
    provider_names: Mapping[str, str] | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/api/content-projects", tags=["content-projects"])
    providers = {
        "llm": "mock",
        "research": "mock",
        "video": "mock",
        **dict(provider_names or {}),
    }

    @router.post(
        "",
        response_model=ContentProjectRead,
        status_code=status.HTTP_201_CREATED,
    )
    async def create_content_project(
        data: ContentProjectCreate,
        principal: Annotated[AuthPrincipal, Depends(auth_guard.require(PERMISSION_CREATE_PROJECT))],
    ) -> ContentProjectRead:
        project = await service.create_project(data, owner_id=principal.user_id)
        await service.append_event(
            project.id,
            "project.created",
            payload={"providers": providers},
        )
        loaded = await service.get_project(project.id)
        if loaded is None:  # pragma: no cover - a committed insert must be readable
            raise HTTPException(status_code=500, detail="Created project could not be loaded")
        return _project_read(loaded, providers=providers)

    @router.get("", response_model=list[ContentProjectSummary])
    async def list_content_projects(
        principal: Annotated[AuthPrincipal, Depends(auth_guard.require(PERMISSION_READ_PROJECT))],
        limit: int = Query(default=50, ge=1, le=100),
        origin: Annotated[ProjectOrigin | None, Query()] = None,
    ) -> list[ContentProjectSummary]:
        owner_id = (
            None if principal.has_permission(PERMISSION_READ_ALL_PROJECTS) else principal.user_id
        )
        projects = await service.list_projects(limit=limit, owner_id=owner_id, origin=origin)
        return [
            ContentProjectSummary.model_validate(project, from_attributes=True)
            for project in projects
        ]

    @router.post(
        "/{project_id}/start",
        response_model=WorkflowStartResponse,
        status_code=status.HTTP_202_ACCEPTED,
    )
    async def start_content_project(
        project_id: str,
        principal: Annotated[AuthPrincipal, Depends(auth_guard.require(PERMISSION_UPDATE_PROJECT))],
    ) -> WorkflowStartResponse:
        await _require_accessible_project(service, project_id, principal)
        try:
            job = await runner.enqueue(project_id)
        except ProjectNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
            ) from exc
        except ProjectStartConflictError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Project cannot start from status '{exc.current_status}'",
            ) from exc
        return WorkflowStartResponse(project_id=project_id, job_id=job.id)

    @router.post(
        "/{project_id}/strategy-selection",
        response_model=WorkflowStartResponse,
        status_code=status.HTTP_202_ACCEPTED,
    )
    async def select_content_project_strategy(
        project_id: str,
        data: SelectStrategyRequest,
        principal: Annotated[AuthPrincipal, Depends(auth_guard.require(PERMISSION_UPDATE_PROJECT))],
    ) -> WorkflowStartResponse:
        await _require_accessible_project(service, project_id, principal)
        try:
            job = await runner.enqueue_strategy_selection(project_id, data.strategy_id)
        except ProjectNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
            ) from exc
        except ProjectStartConflictError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Project is not waiting for a strategy selection "
                    f"(status='{exc.current_status}')"
                ),
            ) from exc
        except InvalidStrategySelectionError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Selected strategy does not belong to this project",
            ) from exc
        return WorkflowStartResponse(project_id=project_id, job_id=job.id)

    @router.post(
        "/{project_id}/agent-decisions",
        response_model=WorkflowStartResponse,
        status_code=status.HTTP_202_ACCEPTED,
    )
    async def decide_content_project_agent(
        project_id: str,
        data: AgentDecisionRequest,
        principal: Annotated[AuthPrincipal, Depends(auth_guard.require(PERMISSION_UPDATE_PROJECT))],
    ) -> WorkflowStartResponse:
        await _require_accessible_project(service, project_id, principal)
        try:
            job = await runner.enqueue_agent_decision(project_id, data)
        except ProjectNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
            ) from exc
        except ProjectStartConflictError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Project is not waiting for this Agent decision "
                    f"(status='{exc.current_status}')"
                ),
            ) from exc
        except InvalidStrategySelectionError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Selected strategy does not belong to this project",
            ) from exc
        return WorkflowStartResponse(project_id=project_id, job_id=job.id)

    @router.post(
        "/{project_id}/cancel",
        response_model=WorkflowCancelResponse,
    )
    async def cancel_content_project(
        project_id: str,
        principal: Annotated[AuthPrincipal, Depends(auth_guard.require(PERMISSION_CANCEL_PROJECT))],
    ) -> WorkflowCancelResponse:
        await _require_accessible_project(service, project_id, principal)
        try:
            await runner.cancel(project_id)
        except ProjectNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
            ) from exc
        except ProjectStartConflictError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Project cannot be cancelled from status '{exc.current_status}'",
            ) from exc
        return WorkflowCancelResponse(project_id=project_id)

    @router.get("/{project_id}", response_model=ContentProjectRead)
    async def get_content_project(
        project_id: str,
        principal: Annotated[AuthPrincipal, Depends(auth_guard.require(PERMISSION_READ_PROJECT))],
    ) -> ContentProjectRead:
        return _project_read(
            await _require_accessible_project(service, project_id, principal),
            providers=providers,
        )

    @router.get("/{project_id}/events", response_model=list[ProjectEventRead])
    async def get_content_project_events(
        project_id: str,
        principal: Annotated[AuthPrincipal, Depends(auth_guard.require(PERMISSION_READ_PROJECT))],
        after_id: int | None = Query(default=None, ge=1),
    ) -> list[ProjectEventRead]:
        await _require_accessible_project(service, project_id, principal)
        events = await service.list_events(project_id, after_id=after_id)
        return [
            ProjectEventRead(
                id=event.id,
                project_id=event.project_id,
                event_type=event.event_type,
                node_name=event.node_name,
                payload=event.payload,
                created_at=event.created_at,
            )
            for event in events
        ]

    @router.get("/{project_id}/events/stream")
    async def stream_content_project_events(
        project_id: str,
        request: Request,
        principal: Annotated[AuthPrincipal, Depends(auth_guard.require(PERMISSION_READ_PROJECT))],
        after_id: int = Query(default=0, ge=0),
    ) -> StreamingResponse:
        await _require_accessible_project(service, project_id, principal)
        last_event_id = request.headers.get("last-event-id")
        header_cursor = int(last_event_id) if last_event_id and last_event_id.isdigit() else 0
        cursor = max(after_id, header_cursor)

        async def event_stream() -> AsyncIterator[str]:
            nonlocal cursor
            loop = asyncio.get_running_loop()
            heartbeat_at = loop.time()
            project = await _require_project(service, project_id)
            yield _sse_frame(
                "project_state",
                _project_read(project, providers=providers).model_dump_json(),
                retry=2000,
            )
            result_sent = False
            if project.status == "completed":
                result = ContentProjectResult.model_validate(await service.get_result(project_id))
                yield _sse_frame("project_result", result.model_dump_json())
                result_sent = True

            while not await request.is_disconnected():
                events = await service.list_events(project_id, after_id=cursor)
                if events:
                    for event in events:
                        cursor = event.id
                        payload = ProjectEventRead(
                            id=event.id,
                            project_id=event.project_id,
                            event_type=event.event_type,
                            node_name=event.node_name,
                            payload=event.payload,
                            created_at=event.created_at,
                        ).model_dump_json()
                        yield _sse_frame("project_event", payload, event_id=event.id)

                    # Project state is reconciled on the server after every persisted
                    # event batch. The browser only consumes this stream; it does not
                    # need to poll the project and events endpoints in parallel.
                    project = await _require_project(service, project_id)
                    yield _sse_frame(
                        "project_state",
                        _project_read(project, providers=providers).model_dump_json(),
                    )
                    if project.status == "completed" and not result_sent:
                        result = ContentProjectResult.model_validate(
                            await service.get_result(project_id)
                        )
                        yield _sse_frame("project_result", result.model_dump_json())
                        result_sent = True
                    heartbeat_at = loop.time()
                    continue
                if loop.time() - heartbeat_at >= 15:
                    yield ": keep-alive\n\n"
                    heartbeat_at = loop.time()
                await asyncio.sleep(0.25)

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    @router.get("/{project_id}/result", response_model=ContentProjectResult)
    async def get_content_project_result(
        project_id: str,
        principal: Annotated[AuthPrincipal, Depends(auth_guard.require(PERMISSION_READ_PROJECT))],
    ) -> ContentProjectResult:
        project = await _require_accessible_project(service, project_id, principal)
        if project.status != "completed":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Project result is not ready (status='{project.status}')",
            )
        return ContentProjectResult.model_validate(await service.get_result(project_id))

    return router


async def _require_project(service: ContentProjectService, project_id: str) -> ContentProject:
    project = await service.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


async def _require_accessible_project(
    service: ContentProjectService,
    project_id: str,
    principal: AuthPrincipal,
) -> ContentProject:
    project = await _require_project(service, project_id)
    if principal.has_permission(PERMISSION_READ_ALL_PROJECTS):
        return project
    if project.owner_id != principal.user_id:
        # Do not reveal whether another user's project exists.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


def _project_read(
    project: ContentProject,
    *,
    providers: Mapping[str, str] | None = None,
) -> ContentProjectRead:
    artifacts: dict[str, dict[str, Any]] = {}
    for artifact in sorted(project.artifacts, key=lambda item: item.version):
        artifacts[artifact.artifact_type] = artifact.content

    video_task = None
    if project.video_tasks:
        latest_video_task = max(
            project.video_tasks,
            key=lambda item: (item.created_at, item.id),
        )
        video_task = _video_task_read(latest_video_task)

    errors = []
    if project.error:
        errors.append(project.error)

    return ContentProjectRead(
        id=project.id,
        title=project.title,
        request_text=project.request_text,
        status=project.status,
        current_node=project.current_node,
        references=[
            {
                "type": reference.reference_type,
                "id": reference.reference_id,
                "label": reference.label,
                "snapshot": reference.snapshot,
            }
            for reference in sorted(project.references, key=lambda item: item.position)
        ],
        blueprint_id=project.blueprint_id,
        selected_strategy_id=project.selected_strategy_id,
        requested_mode=project.requested_mode,
        origin=project.origin,
        resolved_intent=project.resolved_intent,
        artifacts=artifacts,
        video_task=video_task,
        errors=errors,
        providers={
            "llm": "mock",
            "research": "mock",
            "video": "mock",
            **dict(providers or {}),
        },
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


def _video_task_read(task: VideoTask) -> dict[str, Any]:
    return {
        "task_id": task.external_task_id or task.id,
        "provider": task.provider,
        "is_mock": task.is_mock,
        "status": task.status,
        "progress": task.progress,
        "result_url": task.result_url,
        "error_code": None if task.error is None else task.error.get("code"),
        "error_message": None if task.error is None else task.error.get("message"),
    }


def _sse_frame(
    event: str,
    data: str,
    *,
    event_id: int | None = None,
    retry: int | None = None,
) -> str:
    fields = []
    if event_id is not None:
        fields.append(f"id: {event_id}")
    if retry is not None:
        fields.append(f"retry: {retry}")
    fields.extend((f"event: {event}", f"data: {data}"))
    return "\n".join(fields) + "\n\n"
