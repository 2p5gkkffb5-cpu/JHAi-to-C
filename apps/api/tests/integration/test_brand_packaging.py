import asyncio

import pytest
from httpx import ASGITransport, AsyncClient

from jhai_to_c.config import Settings
from jhai_to_c.main import create_app


async def _wait_for_status(
    client: AsyncClient,
    project_id: str,
    status: str,
) -> dict:
    for _ in range(300):
        response = await client.get(f"/api/content-projects/{project_id}")
        assert response.status_code == 200
        project = response.json()
        if project["status"] == status:
            return project
        if project["status"] == "failed":
            pytest.fail(str(project.get("errors")))
        await asyncio.sleep(0.01)
    pytest.fail(f"project did not reach {status}")


@pytest.mark.asyncio
async def test_selected_packaging_service_finishes_without_video_generation(tmp_path) -> None:
    app = create_app(
        Settings(
            _env_file=None,
            app_env="test",
            database_url=f"sqlite+aiosqlite:///{tmp_path / 'packaging.db'}",
            langgraph_checkpoint_path=str(tmp_path / "packaging-checkpoints.db"),
            llm_provider="mock",
            research_provider="mock",
            image_provider="disabled",
            video_provider="mock",
            mock_provider_latency_ms=0,
        )
    )

    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            created = await client.post(
                "/api/content-projects",
                json={
                    "title": "山屿店铺包装",
                    "request_text": "店铺名叫山屿，主营手作陶瓷，面向年轻家庭，希望自然克制。",
                    "requested_mode": "brand_packaging",
                    "references": [
                        {
                            "type": "image",
                            "id": "uploaded-product-photo",
                            "label": "@陶瓷产品图.jpg",
                            "snapshot": {"url": "https://example.com/product.jpg"},
                        }
                    ],
                },
            )
            assert created.status_code == 201
            project_id = created.json()["id"]
            start = await client.post(f"/api/content-projects/{project_id}/start")
            assert start.status_code == 202

            waiting = await _wait_for_status(client, project_id, "waiting_approval")
            assert waiting["current_node"] == "brand_packaging"
            assert waiting["resolved_intent"] == "brand_packaging"
            assert waiting["artifacts"]["brand_packaging"]["assets"]
            assert waiting["video_task"] is None

            approved = await client.post(
                f"/api/content-projects/{project_id}/agent-decisions",
                json={"node_name": "brand_packaging", "action": "approve"},
            )
            assert approved.status_code == 202
            await _wait_for_status(client, project_id, "completed")

            result = (await client.get(f"/api/content-projects/{project_id}/result")).json()
            assert result["resolved_intent"] == "brand_packaging"
            assert result["brand_packaging"]["brand_foundation"]["brand_name"]
            assert result["video_task"] is None
            assert result["copywriting"] == {}

            events = (await client.get(f"/api/content-projects/{project_id}/events")).json()
            assert [
                event["node_name"]
                for event in events
                if event["event_type"] == "node.completed"
            ] == ["intent_router", "director", "research", "brand_packaging"]
