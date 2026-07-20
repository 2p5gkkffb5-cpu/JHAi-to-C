import asyncio

import pytest
from sqlalchemy import event, func, select

from jhai_to_c.db import (
    AgentRun,
    Artifact,
    ContentProject,
    Database,
    ProjectEvent,
    WorkflowJob,
)
from jhai_to_c.services import (
    ContentProjectService,
    DeploymentCutoverConflictError,
)


async def _create_orphan_project(service: ContentProjectService):
    project = await service.create_project(title="orphan", request_text="生成视频")
    job = await service.create_start_job(project.id)
    await service.finish_job(job.id, status="completed")
    await service.update_status(project.id, "running", current_node="storyboard")
    running_run = await service.start_agent_run(
        project.id,
        agent_name="storyboard_agent",
        node_name="storyboard",
    )
    return project, running_run


async def _load_orphan_terminalization_state(database: Database, project_id: str):
    async with database.session_factory() as session:
        project = await session.get(ContentProject, project_id)
        runs = list(
            (
                await session.scalars(
                    select(AgentRun)
                    .where(AgentRun.project_id == project_id)
                    .order_by(AgentRun.created_at)
                )
            ).all()
        )
        events = list(
            (
                await session.scalars(
                    select(ProjectEvent)
                    .where(
                        ProjectEvent.project_id == project_id,
                        ProjectEvent.event_type == "workflow.failed",
                    )
                    .order_by(ProjectEvent.id)
                )
            ).all()
        )
    return project, runs, events


@pytest.mark.asyncio
async def test_deployment_job_terminalization_is_atomic_and_idempotent(tmp_path) -> None:
    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'cutover.db'}")
    await database.create_schema()
    service = ContentProjectService(database.session_factory)
    project = await service.create_project(title="cutover", request_text="生成视频")
    job = await service.create_start_job(project.id)
    await service.update_status(project.id, "running", current_node="storyboard")
    completed_run = await service.start_agent_run(
        project.id,
        agent_name="director",
        node_name="director",
    )
    await service.finish_agent_run(completed_run.id)
    running_run = await service.start_agent_run(
        project.id,
        agent_name="research",
        node_name="research",
    )
    await service.save_artifact(project.id, "creative_brief", {"kept": True})

    assert await service.terminalize_deployment_job(job.id) is True
    assert await service.terminalize_deployment_job(job.id) is False
    snapshot = await service.deployment_gate_snapshot()

    async with database.session_factory() as session:
        loaded_job = await session.get(WorkflowJob, job.id)
        loaded_project = await service.get_project(project.id)
        runs = list(
            (
                await session.scalars(
                    select(AgentRun)
                    .where(AgentRun.project_id == project.id)
                    .order_by(AgentRun.created_at)
                )
            ).all()
        )
        event_count = await session.scalar(
            select(func.count())
            .select_from(ProjectEvent)
            .where(
                ProjectEvent.project_id == project.id,
                ProjectEvent.event_type == "workflow.failed",
            )
        )
        artifact_count = await session.scalar(
            select(func.count()).select_from(Artifact).where(Artifact.project_id == project.id)
        )

    assert loaded_job.status == "failed"
    assert loaded_job.last_error == "deployment_cutover"
    assert loaded_project.status == "failed"
    assert loaded_project.current_node == "storyboard"
    assert loaded_project.error["code"] == "deployment_cutover"
    assert [(run.id, run.status) for run in runs] == [
        (completed_run.id, "completed"),
        (running_run.id, "failed"),
    ]
    assert event_count == 1
    assert artifact_count == 1
    assert snapshot == {
        "pending_count": 0,
        "running_count": 0,
        "running_agent_run_count": 0,
        "orphan_project_count": 0,
        "concurrent_project_count": 0,
    }
    await database.dispose()


@pytest.mark.asyncio
async def test_deployment_terminalization_rejects_concurrent_active_jobs(tmp_path) -> None:
    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'concurrent.db'}")
    await database.create_schema()
    service = ContentProjectService(database.session_factory)
    project = await service.create_project(title="cutover", request_text="生成视频")
    first_job = await service.create_start_job(project.id)
    await service.create_job(project.id)

    with pytest.raises(DeploymentCutoverConflictError):
        await service.terminalize_deployment_job(first_job.id)
    snapshot = await service.deployment_gate_snapshot()
    assert snapshot["pending_count"] == 2
    assert snapshot["concurrent_project_count"] == 1
    await database.dispose()


@pytest.mark.asyncio
async def test_orphan_project_terminalization_is_sequentially_idempotent(tmp_path) -> None:
    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'orphan-sequential.db'}")
    await database.create_schema()
    service = ContentProjectService(database.session_factory)
    project, running_run = await _create_orphan_project(service)

    assert await service.terminalize_orphan_project(project.id) is True
    assert await service.terminalize_orphan_project(project.id) is False

    loaded_project, runs, events = await _load_orphan_terminalization_state(database, project.id)
    assert loaded_project is not None
    assert loaded_project.status == "failed"
    assert loaded_project.current_node == "storyboard"
    assert loaded_project.error["code"] == "deployment_cutover"
    assert [(run.id, run.status) for run in runs] == [(running_run.id, "failed")]
    assert len(events) == 1
    assert events[0].node_name is None
    assert events[0].payload["code"] == "deployment_cutover"
    await database.dispose()


@pytest.mark.asyncio
async def test_orphan_project_terminalization_is_concurrently_idempotent(tmp_path) -> None:
    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'orphan-concurrent.db'}")
    await database.create_schema()
    service = ContentProjectService(database.session_factory)
    project, running_run = await _create_orphan_project(service)

    results = await asyncio.gather(
        service.terminalize_orphan_project(project.id),
        service.terminalize_orphan_project(project.id),
    )

    assert sorted(results) == [False, True]
    loaded_project, runs, events = await _load_orphan_terminalization_state(database, project.id)
    assert loaded_project is not None
    assert loaded_project.status == "failed"
    assert [(run.id, run.status) for run in runs] == [(running_run.id, "failed")]
    assert len(events) == 1
    assert events[0].event_type == "workflow.failed"
    await database.dispose()


@pytest.mark.asyncio
async def test_orphan_project_terminalization_rolls_back_on_event_write_failure(
    tmp_path,
) -> None:
    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'orphan-rollback.db'}")
    await database.create_schema()
    service = ContentProjectService(database.session_factory)
    project, running_run = await _create_orphan_project(service)

    def fail_event_write(
        connection: object,
        cursor: object,
        statement: str,
        parameters: object,
        context: object,
        executemany: bool,
    ) -> None:
        if statement.lstrip().startswith("INSERT INTO project_events"):
            raise RuntimeError("injected project event write failure")

    event.listen(database.engine.sync_engine, "before_cursor_execute", fail_event_write)
    try:
        with pytest.raises(RuntimeError, match="injected project event write failure"):
            await service.terminalize_orphan_project(project.id)
    finally:
        event.remove(database.engine.sync_engine, "before_cursor_execute", fail_event_write)

    (
        rolled_back_project,
        rolled_back_runs,
        rolled_back_events,
    ) = await _load_orphan_terminalization_state(database, project.id)
    assert rolled_back_project is not None
    assert rolled_back_project.status == "running"
    assert rolled_back_project.error is None
    assert rolled_back_project.completed_at is None
    assert [(run.id, run.status) for run in rolled_back_runs] == [(running_run.id, "running")]
    assert rolled_back_runs[0].error is None
    assert rolled_back_runs[0].completed_at is None
    assert rolled_back_events == []

    assert await service.terminalize_orphan_project(project.id) is True
    committed_project, committed_runs, committed_events = await _load_orphan_terminalization_state(
        database, project.id
    )
    assert committed_project is not None
    assert committed_project.status == "failed"
    assert [(run.id, run.status) for run in committed_runs] == [(running_run.id, "failed")]
    assert len(committed_events) == 1
    assert committed_events[0].event_type == "workflow.failed"
    await database.dispose()


@pytest.mark.asyncio
async def test_same_thread_resume_job_is_not_available(tmp_path) -> None:
    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'resume.db'}")
    await database.create_schema()
    service = ContentProjectService(database.session_factory)
    project = await service.create_project(title="resume", request_text="生成视频")
    with pytest.raises(ValueError, match="same_thread_resume_not_supported"):
        await service.create_job(project.id, job_type="resume_project")
    await database.dispose()
