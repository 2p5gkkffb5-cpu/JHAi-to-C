import asyncio

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from jhai_to_c.config import Settings
from jhai_to_c.db import AgentRun, WorkflowJob
from jhai_to_c.main import create_app


async def _create_project(client: AsyncClient, title: str) -> str:
    response = await client.post(
        "/api/content-projects",
        json={
            "title": title,
            "request_text": "生成一条 20 秒商品营销短视频",
            "duration_seconds": 20,
            "aspect_ratio": "9:16",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


async def _wait_for_approval(
    client: AsyncClient,
    project_id: str,
    node_name: str,
) -> dict:
    for _ in range(600):
        response = await client.get(f"/api/content-projects/{project_id}")
        assert response.status_code == 200
        project = response.json()
        if project["status"] == "waiting_approval" and project["current_node"] == node_name:
            return project
        await asyncio.sleep(0.01)
    pytest.fail(f"project did not wait for {node_name} approval")


async def _approve(
    client: AsyncClient,
    project_id: str,
    node_name: str,
    *,
    strategy_id: str | None = None,
) -> None:
    payload = {"node_name": node_name, "action": "approve"}
    if strategy_id is not None:
        payload["strategy_id"] = strategy_id
    response = await client.post(
        f"/api/content-projects/{project_id}/agent-decisions",
        json=payload,
    )
    assert response.status_code == 202, response.text


@pytest.mark.asyncio
async def test_final_retry_feedback_reaches_next_agent_attempt_and_events(tmp_path) -> None:
    app = create_app(
        Settings(
            app_env="test",
            database_url=f"sqlite+aiosqlite:///{tmp_path / 'app.db'}",
            langgraph_checkpoint_path=str(tmp_path / "checkpoints.db"),
            mock_provider_latency_ms=0,
        )
    )
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            project_id = await _create_project(client, "retry-feedback")
            assert (
                await client.post(f"/api/content-projects/{project_id}/start")
            ).status_code == 202
            await _wait_for_approval(client, project_id, "production")

            retry_response = await client.post(
                f"/api/content-projects/{project_id}/agent-decisions",
                json={
                    "node_name": "production",
                    "action": "retry",
                    "feedback": "突出新品的年轻人使用场景",
                },
            )
            assert retry_response.status_code == 202
            await _wait_for_approval(client, project_id, "production")

            events = (await client.get(f"/api/content-projects/{project_id}/events")).json()
            completed = [
                event
                for event in events
                if event["event_type"] == "node.completed" and event["node_name"] == "production"
            ]
            assert [event["payload"]["attempt"] for event in completed] == [1, 2]
            assert all(event["payload"]["tools"] for event in completed)
            assert all(event["payload"]["summary"] for event in completed)
            assert all(event["payload"]["output"]["copywriting"] for event in completed)
            production_trace = [
                event
                for event in events
                if event["event_type"].startswith("trace.") and event["node_name"] == "production"
            ]
            assert [
                (event["payload"]["phase"], event["payload"]["iteration"])
                for event in production_trace
            ] == [
                ("thought", 1),
                ("action", 1),
                ("observation", 1),
                ("thought", 2),
                ("action", 2),
                ("observation", 2),
            ]

            assert (
                await client.post(f"/api/content-projects/{project_id}/cancel")
            ).status_code == 200

        async with app.state.database.session_factory() as session:
            runs = list(
                (
                    await session.scalars(
                        select(AgentRun)
                        .where(
                            AgentRun.project_id == project_id,
                            AgentRun.node_name == "production",
                        )
                        .order_by(AgentRun.attempt)
                    )
                ).all()
            )
            jobs = list(
                (
                    await session.scalars(
                        select(WorkflowJob)
                        .where(WorkflowJob.project_id == project_id)
                        .order_by(WorkflowJob.created_at)
                    )
                ).all()
            )

    assert [run.attempt for run in runs] == [1, 2]
    assert runs[1].input_data["user_feedback"] == "突出新品的年轻人使用场景"
    assert jobs[1].resume_payload == {
        "node_name": "production",
        "action": "retry",
        "feedback": "突出新品的年轻人使用场景",
    }


@pytest.mark.asyncio
async def test_production_retry_feedback_reaches_combined_agent(tmp_path) -> None:
    app = create_app(
        Settings(
            app_env="test",
            database_url=f"sqlite+aiosqlite:///{tmp_path / 'app.db'}",
            langgraph_checkpoint_path=str(tmp_path / "checkpoints.db"),
            mock_provider_latency_ms=0,
        )
    )
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            project_id = await _create_project(client, "nested-retry")
            assert (
                await client.post(f"/api/content-projects/{project_id}/start")
            ).status_code == 202
            await _wait_for_approval(client, project_id, "production")

            retry_response = await client.post(
                f"/api/content-projects/{project_id}/agent-decisions",
                json={
                    "node_name": "production",
                    "action": "retry",
                    "feedback": "把开头改成更直接的痛点提问",
                },
            )
            assert retry_response.status_code == 202
            await _wait_for_approval(client, project_id, "production")
            assert (
                await client.post(f"/api/content-projects/{project_id}/cancel")
            ).status_code == 200

        async with app.state.database.session_factory() as session:
            runs = list(
                (
                    await session.scalars(
                        select(AgentRun)
                        .where(
                            AgentRun.project_id == project_id,
                            AgentRun.node_name == "production",
                        )
                        .order_by(AgentRun.attempt)
                    )
                ).all()
            )

    assert [run.attempt for run in runs] == [1, 2]
    assert runs[1].input_data["user_feedback"] == "把开头改成更直接的痛点提问"


@pytest.mark.asyncio
async def test_duplicate_agent_decision_is_claimed_once(tmp_path) -> None:
    app = create_app(
        Settings(
            app_env="test",
            database_url=f"sqlite+aiosqlite:///{tmp_path / 'app.db'}",
            langgraph_checkpoint_path=str(tmp_path / "checkpoints.db"),
            mock_provider_latency_ms=30,
        )
    )
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            project_id = await _create_project(client, "duplicate-decision")
            assert (
                await client.post(f"/api/content-projects/{project_id}/start")
            ).status_code == 202
            await _wait_for_approval(client, project_id, "production")

            responses = await asyncio.gather(
                *(
                    client.post(
                        f"/api/content-projects/{project_id}/agent-decisions",
                        json={"node_name": "production", "action": "approve"},
                    )
                    for _ in range(2)
                )
            )
            assert sorted(response.status_code for response in responses) == [202, 409]
            events = (await client.get(f"/api/content-projects/{project_id}/events")).json()
            assert not any(
                event["event_type"] == "workflow.waiting_approval"
                and event["node_name"] in {"director", "research"}
                for event in events
            )


@pytest.mark.asyncio
async def test_cancel_running_job_is_atomic_and_worker_continues(tmp_path) -> None:
    app = create_app(
        Settings(
            app_env="test",
            database_url=f"sqlite+aiosqlite:///{tmp_path / 'app.db'}",
            langgraph_checkpoint_path=str(tmp_path / "checkpoints.db"),
            mock_provider_latency_ms=500,
        )
    )
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            project_id = await _create_project(client, "cancel-running")
            assert (
                await client.post(f"/api/content-projects/{project_id}/start")
            ).status_code == 202

            for _ in range(200):
                events = (await client.get(f"/api/content-projects/{project_id}/events")).json()
                if any(
                    event["event_type"] == "node.started"
                    and event["node_name"] == "director"
                    for event in events
                ):
                    break
                await asyncio.sleep(0.01)
            else:
                pytest.fail("director did not start")

            await app.state.project_service.create_or_update_video_task(
                project_id,
                provider="mock",
                is_mock=True,
                status="processing",
                external_task_id="cancel-me",
                progress=0.4,
            )
            cancel_response = await client.post(f"/api/content-projects/{project_id}/cancel")
            assert cancel_response.status_code == 200
            assert cancel_response.json() == {
                "project_id": project_id,
                "status": "cancelled",
            }
            assert (
                await client.post(f"/api/content-projects/{project_id}/cancel")
            ).status_code == 200

            project = (await client.get(f"/api/content-projects/{project_id}")).json()
            assert project["status"] == "cancelled"
            assert project["video_task"]["status"] == "cancelled"
            assert project["video_task"]["error_code"] == "cancelled_by_user"
            events = (await client.get(f"/api/content-projects/{project_id}/events")).json()
            assert sum(event["event_type"] == "workflow.cancelled" for event in events) == 1

            next_project_id = await _create_project(client, "worker-survives")
            assert (
                await client.post(f"/api/content-projects/{next_project_id}/start")
            ).status_code == 202
            await _wait_for_approval(client, next_project_id, "production")
            assert (
                await client.post(f"/api/content-projects/{next_project_id}/cancel")
            ).status_code == 200

        async with app.state.database.session_factory() as session:
            cancelled_job = await session.scalar(
                select(WorkflowJob).where(WorkflowJob.project_id == project_id)
            )
            cancelled_run = await session.scalar(
                select(AgentRun).where(AgentRun.project_id == project_id)
            )

    assert cancelled_job is not None and cancelled_job.status == "cancelled"
    assert cancelled_run is not None and cancelled_run.status == "cancelled"
