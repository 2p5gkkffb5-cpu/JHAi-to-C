from enum import StrEnum
from typing import Any

from pydantic import Field

from .common import ContractModel


class VideoTaskStatus(StrEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class VideoGenerationRequest(ContractModel):
    project_id: str = Field(min_length=1, max_length=128)
    prompt: str = Field(min_length=1, max_length=10_000)
    negative_prompt: str = Field(default="", max_length=3000)
    duration_seconds: int = Field(ge=5, le=180)
    aspect_ratio: str = Field(min_length=3, max_length=10)
    reference_urls: list[str] = Field(default_factory=list, max_length=10)
    provider_parameters: dict[str, Any] = Field(default_factory=dict)


class VideoTask(ContractModel):
    task_id: str = Field(min_length=1, max_length=256)
    provider: str = Field(min_length=1, max_length=100)
    is_mock: bool
    status: VideoTaskStatus
    progress: float | None = Field(default=None, ge=0, le=1)
    result_url: str | None = Field(default=None, max_length=2000)
    error_code: str | None = Field(default=None, max_length=100)
    error_message: str | None = Field(default=None, max_length=2000)
