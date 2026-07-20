import pytest
from httpx import ASGITransport, AsyncClient

from jhai_to_c.config import Settings
from jhai_to_c.main import create_app


@pytest.mark.asyncio
async def test_real_provider_flags_are_exposed_without_mock_fallback(tmp_path) -> None:
    settings = Settings(
        app_env="test",
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'app.db'}",
        langgraph_checkpoint_path=str(tmp_path / "checkpoints.db"),
        llm_provider="real",
        llm_api_key="grsai-llm-key",
        llm_model="gemini-3.1-pro",
        research_provider="bocha",
        research_api_key="bocha-research-key",
        video_provider="real",
        video_api_key="ark-video-key",
        video_model="ark-seedance-endpoint",
    )
    app = create_app(settings)

    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/content-projects",
                json={
                    "title": "真实 Provider 配置测试",
                    "request_text": "创建一个十秒商品广告",
                    "duration_seconds": 10,
                },
            )

    assert response.status_code == 201
    assert response.json()["providers"] == {
        "llm": "grsai",
        "research": "bocha",
        "video": "seedance",
        "video_understanding": "gemini-video+ffmpeg",
    }


@pytest.mark.parametrize(
    ("settings_overrides", "missing_setting"),
    [
        ({"llm_provider": "real"}, "LLM_API_KEY"),
        (
            {"llm_provider": "real", "llm_api_key": "key"},
            "LLM_MODEL",
        ),
        ({"research_provider": "bocha"}, "RESEARCH_API_KEY"),
        ({"image_provider": "real"}, "IMAGE_API_KEY"),
        (
            {"image_provider": "real", "image_api_key": "key"},
            "IMAGE_MODEL",
        ),
        ({"video_provider": "real"}, "VIDEO_API_KEY"),
        (
            {"video_provider": "real", "video_api_key": "key"},
            "VIDEO_MODEL",
        ),
    ],
)
def test_real_provider_configuration_fails_fast(
    settings_overrides: dict[str, str],
    missing_setting: str,
) -> None:
    with pytest.raises(ValueError, match=missing_setting):
        create_app(Settings(**settings_overrides))


@pytest.mark.asyncio
async def test_yg_video_gateway_does_not_require_video_model(tmp_path) -> None:
    app = create_app(
        Settings(
            app_env="test",
            database_url=f"sqlite+aiosqlite:///{tmp_path / 'yg-app.db'}",
            langgraph_checkpoint_path=str(tmp_path / "yg-checkpoints.db"),
            video_provider="real",
            yg_seedance_base_url="http://video.example.test",
            yg_seedance_api_key="yg-secret",
        )
    )

    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/content-projects",
                json={
                    "title": "YG Provider 配置测试",
                    "request_text": "创建一个十秒商品广告",
                    "duration_seconds": 10,
                },
            )

    assert response.status_code == 201
    assert response.json()["providers"]["video"] == "seedance"
