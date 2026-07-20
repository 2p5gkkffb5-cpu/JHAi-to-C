from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from math import ceil

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import SecretStr

from jhai_to_c.api import (
    AuthGuard,
    build_assets_router,
    build_auth_router,
    build_content_projects_router,
    build_images_router,
)
from jhai_to_c.config import Settings
from jhai_to_c.db import Database
from jhai_to_c.providers.interfaces import (
    AgentModelProvider,
    ImageProvider,
    ResearchProvider,
    VideoProvider,
    VideoUnderstandingProvider,
)
from jhai_to_c.providers.mock import (
    DeterministicMockAgentModelProvider,
    DeterministicMockResearchProvider,
    DeterministicMockVideoProvider,
    DeterministicMockVideoUnderstandingProvider,
    MockProviderControl,
)
from jhai_to_c.providers.real import (
    BochaResearchProvider,
    FFmpegVideoUnderstandingProvider,
    RealAgentModelProvider,
    RealImageProvider,
    RealVideoProvider,
)
from jhai_to_c.runner import WorkflowRunner
from jhai_to_c.services import AuthService, ContentProjectService, UploadedAssetService
from jhai_to_c.workflow import build_content_project_graph


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or Settings()
    database = Database(app_settings.database_url)
    service = ContentProjectService(database.session_factory)
    auth_service = AuthService(
        database.session_factory,
        session_days=app_settings.auth_session_days,
    )
    auth_guard = AuthGuard(auth_service, enabled=app_settings.resolved_auth_enabled)
    asset_service = UploadedAssetService(
        database.session_factory,
        app_settings.asset_upload_dir,
        max_bytes=app_settings.asset_max_bytes,
        max_video_bytes=app_settings.asset_video_max_bytes,
    )
    mock_control = MockProviderControl(
        latency_ms=app_settings.mock_provider_latency_ms,
        scenario=app_settings.mock_provider_scenario,
    )
    agent_model_provider = _build_agent_model_provider(app_settings, mock_control)
    research_provider = _build_research_provider(app_settings, mock_control)
    image_provider = _build_image_provider(app_settings)
    video_provider = _build_video_provider(app_settings, mock_control)
    video_understanding_provider = _build_video_understanding_provider(
        app_settings,
        mock_control,
        asset_service=asset_service,
        agent_model_provider=agent_model_provider,
    )
    provider_names = {
        "llm": agent_model_provider.provider_name,
        "research": research_provider.provider_name,
        "video": video_provider.provider_name,
        "video_understanding": video_understanding_provider.provider_name,
    }

    def build_graph(
        *,
        checkpointer: object | None = None,
        video_status_callback=None,
    ):
        return build_content_project_graph(
            agent_model_provider=agent_model_provider,
            research_provider=research_provider,
            video_provider=video_provider,
            video_understanding_provider=video_understanding_provider,
            video_max_status_polls=max(
                1,
                ceil(
                    app_settings.video_task_timeout_seconds
                    / app_settings.video_poll_interval_seconds
                ),
            ),
            video_status_callback=video_status_callback,
            video_reference_resolver=asset_service.inline_image_data_url,
            checkpointer=checkpointer,
            require_final_approval=True,
            enable_intent_routing=True,
        )

    runner = WorkflowRunner(
        service,
        app_settings.langgraph_checkpoint_path,
        graph_builder=build_graph,
        provider_names=provider_names,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # Tests get isolated tables; development/demo databases must use Alembic.
        if app_settings.app_env == "test":
            await database.create_schema()
        await auth_service.ensure_default_roles()
        await runner.start()
        app.state.settings = app_settings
        app.state.database = database
        app.state.project_service = service
        app.state.asset_service = asset_service
        app.state.auth_service = auth_service
        app.state.workflow_runner = runner
        try:
            yield
        finally:
            await runner.stop()
            await database.dispose()

    app = FastAPI(
        title="JHAi-to-C API",
        version="0.3.0",
        lifespan=lifespan,
    )
    cors_origins = [
        origin.strip() for origin in app_settings.cors_origins.split(",") if origin.strip()
    ]
    if cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    app.include_router(
        build_auth_router(
            auth_service,
            auth_guard,
            cookie_secure=app_settings.auth_cookie_secure,
            session_days=app_settings.auth_session_days,
        )
    )
    app.include_router(
        build_assets_router(
            asset_service,
            auth_guard,
            public_base_url=app_settings.asset_public_base_url,
        )
    )
    app.include_router(
        build_content_projects_router(
            service,
            runner,
            auth_guard,
            provider_names=provider_names,
        )
    )
    app.include_router(build_images_router(image_provider, auth_guard))
    return app


def _build_agent_model_provider(
    settings: Settings,
    mock_control: MockProviderControl,
) -> AgentModelProvider:
    if settings.llm_provider == "mock":
        return DeterministicMockAgentModelProvider(mock_control)
    return RealAgentModelProvider(
        api_key=_required_secret(settings.llm_api_key, "LLM_API_KEY"),
        base_url=settings.llm_api_base_url,
        model=_required_text(settings.llm_model, "LLM_MODEL"),
        timeout_seconds=settings.llm_timeout_seconds,
        max_retries=settings.llm_max_retries,
        retry_base_delay_seconds=settings.llm_retry_base_delay_seconds,
    )


def _build_video_understanding_provider(
    settings: Settings,
    mock_control: MockProviderControl,
    *,
    asset_service: UploadedAssetService,
    agent_model_provider: AgentModelProvider,
) -> VideoUnderstandingProvider:
    if settings.llm_provider == "mock":
        return DeterministicMockVideoUnderstandingProvider(mock_control)
    return FFmpegVideoUnderstandingProvider(
        asset_service=asset_service,
        model_provider=agent_model_provider,
        max_download_bytes=settings.asset_video_max_bytes,
        native_video_enabled=settings.video_understanding_native_enabled,
        native_video_max_bytes=settings.video_understanding_native_max_bytes,
        native_video_timeout_seconds=(
            settings.video_understanding_native_timeout_seconds
        ),
    )


def _build_research_provider(
    settings: Settings,
    mock_control: MockProviderControl,
) -> ResearchProvider:
    if settings.research_provider == "mock":
        return DeterministicMockResearchProvider(mock_control)
    return BochaResearchProvider(
        api_key=_required_secret(settings.research_api_key, "RESEARCH_API_KEY"),
        base_url=settings.research_api_base_url,
        request_timeout_seconds=settings.research_request_timeout_seconds,
        max_results=settings.research_max_results,
        max_retries=settings.research_max_retries,
        retry_base_delay_seconds=settings.research_retry_base_delay_seconds,
    )


def _build_image_provider(settings: Settings) -> ImageProvider | None:
    if settings.image_provider == "disabled":
        return None
    return RealImageProvider(
        api_key=_required_secret(settings.image_api_key, "IMAGE_API_KEY"),
        base_url=settings.image_api_base_url,
        model=_required_text(settings.image_model, "IMAGE_MODEL"),
        request_timeout_seconds=settings.image_request_timeout_seconds,
    )


def _build_video_provider(
    settings: Settings,
    mock_control: MockProviderControl,
) -> VideoProvider:
    if settings.video_provider == "mock":
        return DeterministicMockVideoProvider(mock_control)

    if settings.yg_seedance_base_url is not None or settings.yg_seedance_api_key is not None:
        return RealVideoProvider(
            api_key=_required_secret(
                settings.yg_seedance_api_key,
                "YG_SEEDANCE_API_KEY",
            ),
            base_url=_required_text(
                settings.yg_seedance_base_url,
                "YG_SEEDANCE_BASE_URL",
            ),
            model=_required_text(
                settings.yg_seedance_model,
                "YG_SEEDANCE_MODEL",
            ),
            generation_path=settings.yg_seedance_video_generation_path,
            status_path_template=settings.yg_seedance_video_status_path_template,
            request_timeout_seconds=settings.video_request_timeout_seconds,
            poll_interval_seconds=settings.video_poll_interval_seconds,
        )

    return RealVideoProvider(
        api_key=_required_secret(settings.video_api_key, "VIDEO_API_KEY"),
        base_url=settings.video_api_base_url,
        model=_required_text(settings.video_model, "VIDEO_MODEL"),
        request_timeout_seconds=settings.video_request_timeout_seconds,
        poll_interval_seconds=settings.video_poll_interval_seconds,
    )


def _required_secret(value: SecretStr | None, setting_name: str) -> str:
    if value is None:
        raise ValueError(f"{setting_name} is required when its provider is set to real")
    return _required_text(value.get_secret_value(), setting_name)


def _required_text(value: str | None, setting_name: str) -> str:
    if value is None or not value.strip():
        raise ValueError(f"{setting_name} is required when its provider is set to real")
    return value.strip()


app = create_app()
