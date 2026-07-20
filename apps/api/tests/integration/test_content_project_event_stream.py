import pytest
from httpx import ASGITransport, AsyncClient

from jhai_to_c.config import Settings
from jhai_to_c.main import create_app
from jhai_to_c.services import system_principal


class _ConnectedRequest:
    headers: dict[str, str] = {}

    async def is_disconnected(self) -> bool:
        return False


@pytest.mark.asyncio
async def test_event_stream_pushes_project_state_with_persisted_events(tmp_path) -> None:
    settings = Settings(
        _env_file=None,
        app_env="test",
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'event-stream.db'}",
        langgraph_checkpoint_path=str(tmp_path / "event-stream-checkpoints.db"),
        mock_provider_latency_ms=0,
    )
    app = create_app(settings)

    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/content-projects",
                json={"title": "SSE 状态推送", "request_text": "验证服务端事件流"},
            )
        project_id = response.json()["id"]
        content_projects_router = next(
            route.original_router
            for route in app.routes
            if any(
                getattr(candidate, "path", None)
                == "/api/content-projects/{project_id}/events/stream"
                for candidate in getattr(getattr(route, "original_router", None), "routes", ())
            )
        )
        stream_route = next(
            route
            for route in content_projects_router.routes
            if route.path == "/api/content-projects/{project_id}/events/stream"
        )
        stream_response = await stream_route.endpoint(
            project_id=project_id,
            request=_ConnectedRequest(),
            principal=system_principal(),
            after_id=0,
        )
        iterator = stream_response.body_iterator
        frames = [await anext(iterator) for _ in range(3)]
        await iterator.aclose()

    assert "event: project_state" in frames[0]
    assert '"status":"draft"' in frames[0]
    assert "event: project_event" in frames[1]
    assert '"event_type":"project.created"' in frames[1]
    assert "event: project_state" in frames[2]
