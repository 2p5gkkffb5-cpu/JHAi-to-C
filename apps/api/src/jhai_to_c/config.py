from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment contract for the JHAi-to-C application."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: Literal["development", "test", "demo"] = "development"
    app_host: str = "127.0.0.1"
    app_port: int = Field(default=8000, ge=1, le=65535)
    app_log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    demo_mode: bool = False

    database_url: str = "sqlite+aiosqlite:///./data/app.db"
    langgraph_checkpoint_path: str = "./data/checkpoints.db"
    cors_origins: str = "http://localhost:5174"

    # This test branch runs without login by default. Deployments can opt in explicitly.
    auth_enabled: bool = False
    auth_session_days: int = Field(default=30, ge=1, le=365)
    auth_cookie_secure: bool = False

    asset_upload_dir: str = "./data/uploads"
    asset_max_bytes: int = Field(
        default=10 * 1024 * 1024,
        ge=1024 * 1024,
        le=100 * 1024 * 1024,
    )
    asset_video_max_bytes: int = Field(
        default=100 * 1024 * 1024,
        ge=10 * 1024 * 1024,
        le=500 * 1024 * 1024,
    )
    asset_public_base_url: str | None = None

    llm_provider: Literal["mock", "real"] = "mock"
    llm_api_key: SecretStr | None = None
    llm_model: str | None = None
    llm_api_base_url: str = "https://grsai.dakka.com.cn/v1"
    llm_timeout_seconds: int = Field(default=60, ge=1, le=600)
    llm_max_retries: int = Field(default=2, ge=0, le=10)
    llm_retry_base_delay_seconds: float = Field(default=0.5, ge=0, le=30)

    video_understanding_native_enabled: bool = True
    video_understanding_native_max_bytes: int = Field(
        default=20 * 1024 * 1024,
        ge=1024 * 1024,
        le=100 * 1024 * 1024,
    )
    video_understanding_native_timeout_seconds: int = Field(
        default=60,
        ge=1,
        le=600,
    )

    research_provider: Literal["mock", "bocha"] = "mock"
    research_api_key: SecretStr | None = None
    research_api_base_url: str = "https://api.bocha.cn/v1"
    research_request_timeout_seconds: int = Field(default=30, ge=1, le=300)
    research_max_results: int = Field(default=8, ge=1, le=50)
    research_max_retries: int = Field(default=2, ge=0, le=10)
    research_retry_base_delay_seconds: float = Field(default=0.5, ge=0, le=30)

    image_provider: Literal["disabled", "real"] = "disabled"
    image_api_key: SecretStr | None = None
    image_model: str | None = None
    image_api_base_url: str = "https://grsai.dakka.com.cn/v1"
    image_request_timeout_seconds: int = Field(default=180, ge=1, le=600)

    video_provider: Literal["mock", "real"] = "mock"
    video_api_key: SecretStr | None = None
    video_model: str | None = None
    video_api_base_url: str = "https://ark.cn-beijing.volces.com/api/v3"
    video_request_timeout_seconds: int = Field(default=30, ge=1, le=300)
    video_poll_interval_seconds: int = Field(default=15, ge=1, le=60)
    video_task_timeout_seconds: int = Field(default=900, ge=30, le=3600)

    yg_seedance_base_url: str | None = None
    yg_seedance_api_key: SecretStr | None = None
    yg_seedance_model: str = "doubao-seedance-2.0"
    yg_seedance_video_generation_path: str = (
        "/api/v3/contents/generations/tasks?beta=true"
    )
    yg_seedance_video_status_path_template: str = (
        "/api/v3/contents/generations/tasks/{task_id}?beta=true"
    )

    mock_provider_latency_ms: int = Field(default=250, ge=0, le=30_000)
    mock_provider_scenario: Literal[
        "success",
        "review_fail",
        "video_fail",
        "validation_error",
        "provider_error",
        "coordinator_error",
        "coordinator_invalid_reference",
        "copywriter_error",
        "storyboard_error",
        "video_prompt_error",
    ] = "success"

    @property
    def resolved_auth_enabled(self) -> bool:
        return self.auth_enabled
