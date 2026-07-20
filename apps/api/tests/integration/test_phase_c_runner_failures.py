import asyncio

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from jhai_to_c.config import Settings
from jhai_to_c.db import AgentRun
from jhai_to_c.main import create_app


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "scenario",
    ),
    [
        ("coordinator_error",),
        ("copywriter_error",),
        ("storyboard_error",),
        ("video_prompt_error",),
    ],
)
async def test_nested_failures_have_one_public_projection(
    tmp_path,
    scenario,
) -> None:
    app = create_app(
        Settings(
            app_env="test",
            database_url=f"sqlite+aiosqlite:///{tmp_path / 'app.db'}",
            langgraph_checkpoint_path=str(tmp_path / "checkpoints.db"),
            mock_provider_latency_ms=0,
            mock_provider_scenario=scenario,
        )
    )
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            created = (
                await client.post(
                    "/api/content-projects",
                    json={
                        "title": scenario,
                        "request_text": "生成一条 20 秒商品营销短视频",
                        "duration_seconds": 20,
                        "aspect_ratio": "9:16",
                    },
                )
            ).json()
            project_id = created["id"]
            assert (
                await client.post(f"/api/content-projects/{project_id}/start")
            ).status_code == 202

            for _ in range(200):
                project = (await client.get(f"/api/content-projects/{project_id}")).json()
                if project["status"] == "failed":
                    break
                await asyncio.sleep(0.01)
            else:
                pytest.fail("failure scenario did not terminate")
            for _ in range(100):
                events = (await client.get(f"/api/content-projects/{project_id}/events")).json()
                if any(event["event_type"] == "workflow.failed" for event in events):
                    break
                await asyncio.sleep(0.01)
            else:
                pytest.fail("workflow.failed was not persisted")

        async with app.state.database.session_factory() as session:
            all_runs = list(
                (
                    await session.scalars(
                        select(AgentRun)
                        .where(AgentRun.project_id == project_id)
                        .order_by(AgentRun.created_at)
                    )
                ).all()
            )

    runs = [run for run in all_runs if run.node_name == "production"]
    assert project["current_node"] == "production"
    assert [(run.node_name, run.status) for run in runs] == [("production", "failed")]
    assert all(run.status != "running" for run in all_runs)
    assert set(project["artifacts"]) & {"copywriting", "storyboard", "video_prompt"} == (
        set()
    )
    assert [event["node_name"] for event in events if event["event_type"] == "node.failed"] == (
        ["production"]
    )
    assert sum(event["event_type"] == "workflow.failed" for event in events) == 1
    assert sum(event["node_name"] == "production" for event in events) >= 1
