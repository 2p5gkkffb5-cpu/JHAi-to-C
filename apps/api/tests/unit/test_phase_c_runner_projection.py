from types import SimpleNamespace

import pytest

from jhai_to_c.runner import ExecutionState, WorkflowRunner


class RecordingService:
    def __init__(self) -> None:
        self.status_updates = []
        self.events = []
        self.jobs = []

    async def update_status(self, project_id, status, **kwargs):
        self.status_updates.append((project_id, status, kwargs))

    async def append_event(self, project_id, event_type, **kwargs):
        self.events.append((project_id, event_type, kwargs))

    async def finish_job(self, job_id, **kwargs):
        self.jobs.append((job_id, kwargs))

    async def finish_agent_run(self, run_id, **kwargs):  # pragma: no cover - no active run
        raise AssertionError((run_id, kwargs))


@pytest.mark.asyncio
async def test_combined_production_failure_has_one_public_projection() -> None:
    service = RecordingService()
    runner = WorkflowRunner(service, "/tmp/unused-checkpoint.db")
    execution = ExecutionState()
    await runner._handle_task_event(
        "project",
        (),
        {
            "id": "production-task",
            "name": "production",
            "error": "production generation failed",
        },
        execution,
    )
    await runner._fail_job(
        SimpleNamespace(id="job", project_id="project"),
        RuntimeError("production generation failed"),
        execution,
    )

    assert execution.failure_node == "production"
    assert service.status_updates[-1][2]["current_node"] == "production"
    assert [event_type for _, event_type, _ in service.events] == [
        "node.failed",
        "trace.observation",
        "workflow.failed",
    ]
    assert sum(event_type == "workflow.failed" for _, event_type, _ in service.events) == 1
