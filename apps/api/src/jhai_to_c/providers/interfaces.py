from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field

from jhai_to_c.contracts.common import ContractModel
from jhai_to_c.contracts.image import ImageGenerationRequest, ImageGenerationResult
from jhai_to_c.contracts.research import ResearchSource
from jhai_to_c.contracts.video import VideoGenerationRequest, VideoTask
from jhai_to_c.contracts.video_clone import (
    VideoCloneAnalysisOutput,
    VideoCloneAnalysisRequest,
    VideoCloneReviewOutput,
    VideoCloneReviewRequest,
)


class StructuredGenerationResult[OutputT: BaseModel](ContractModel):
    output: OutputT
    raw_output: str
    provider: str = Field(min_length=1, max_length=100)
    model: str = Field(min_length=1, max_length=200)
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    duration_ms: int = Field(ge=0)


class ResearchQuery(ContractModel):
    query: str = Field(min_length=1, max_length=1000)
    context: dict[str, Any] = Field(default_factory=dict)


class ResearchProviderResult(ContractModel):
    provider: str = Field(min_length=1, max_length=100)
    is_mock: bool
    sources: list[ResearchSource] = Field(default_factory=list, max_length=50)


@runtime_checkable
class AgentModelProvider(Protocol):
    provider_name: str
    is_mock: bool

    async def generate_structured[OutputT: BaseModel](
        self,
        *,
        system_prompt: str,
        input_data: dict[str, Any],
        output_model: type[OutputT],
        model: str | None = None,
        timeout_seconds: int = 60,
        metadata: dict[str, Any] | None = None,
    ) -> StructuredGenerationResult[OutputT]: ...


@runtime_checkable
class ResearchProvider(Protocol):
    provider_name: str
    is_mock: bool

    async def search(self, *, queries: list[ResearchQuery]) -> ResearchProviderResult: ...


@runtime_checkable
class ImageProvider(Protocol):
    provider_name: str
    is_mock: bool

    async def generate(self, *, request: ImageGenerationRequest) -> ImageGenerationResult: ...


@runtime_checkable
class VideoProvider(Protocol):
    provider_name: str
    is_mock: bool

    async def submit(self, *, request: VideoGenerationRequest) -> VideoTask: ...

    async def get_status(self, *, task_id: str) -> VideoTask: ...


@runtime_checkable
class VideoUnderstandingProvider(Protocol):
    provider_name: str
    is_mock: bool

    async def analyze(
        self,
        *,
        request: VideoCloneAnalysisRequest,
    ) -> VideoCloneAnalysisOutput: ...

    async def review(
        self,
        *,
        request: VideoCloneReviewRequest,
    ) -> VideoCloneReviewOutput: ...
