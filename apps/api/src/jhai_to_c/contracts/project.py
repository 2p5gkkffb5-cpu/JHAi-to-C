from datetime import datetime
from typing import Any, Literal

from pydantic import Field, model_validator

from .common import ContractError, ContractModel, ProjectReference, ProjectStatus
from .intent import RequestedMode, TaskIntent
from .packaging import BrandPackagingOutput
from .video import VideoTask

CreatableProjectOrigin = Literal["agent", "ai_video", "video_clone"]
ProjectOrigin = Literal["agent", "ai_video", "video_clone", "legacy"]


class ContentProjectCreate(ContractModel):
    title: str = Field(min_length=1, max_length=200)
    request_text: str = Field(min_length=1, max_length=5000)
    references: list[ProjectReference] = Field(default_factory=list, max_length=20)
    blueprint_id: str | None = Field(default=None, max_length=128)
    target_platform: str = Field(default="douyin", min_length=1, max_length=50)
    duration_seconds: int = Field(default=20, ge=5, le=180)
    aspect_ratio: Literal["9:16", "16:9", "1:1"] = "9:16"
    requested_mode: RequestedMode = RequestedMode.FULL_CREATION
    origin: CreatableProjectOrigin = "agent"

    @model_validator(mode="after")
    def validate_origin_mode(self) -> "ContentProjectCreate":
        if self.origin == "ai_video" and self.requested_mode != RequestedMode.VIDEO_GENERATION:
            raise ValueError(
                "ai_video origin requires requested_mode=video_generation"
            )
        if self.origin == "video_clone" and self.requested_mode != RequestedMode.VIDEO_CLONE:
            raise ValueError("video_clone origin requires requested_mode=video_clone")
        return self


class ResultProviders(ContractModel):
    llm: str = Field(default="mock", min_length=1, max_length=100)
    research: str = Field(default="mock", min_length=1, max_length=100)
    video: str = Field(default="mock", min_length=1, max_length=100)
    video_understanding: str = Field(
        default="mock-video-understanding", min_length=1, max_length=100
    )


class ContentProjectRead(ContractModel):
    id: str = Field(min_length=1, max_length=128)
    title: str
    request_text: str
    status: ProjectStatus
    current_node: str | None = None
    references: list[ProjectReference] = Field(default_factory=list)
    blueprint_id: str | None = None
    selected_strategy_id: str | None = None
    requested_mode: RequestedMode = RequestedMode.FULL_CREATION
    origin: ProjectOrigin = "agent"
    resolved_intent: TaskIntent | None = None
    artifacts: dict[str, dict[str, Any]] = Field(default_factory=dict)
    video_task: dict[str, Any] | None = None
    errors: list[ContractError] = Field(default_factory=list)
    providers: ResultProviders = Field(default_factory=ResultProviders)
    created_at: datetime
    updated_at: datetime


class ContentProjectSummary(ContractModel):
    id: str = Field(min_length=1, max_length=128)
    title: str
    request_text: str
    status: ProjectStatus
    requested_mode: RequestedMode = RequestedMode.FULL_CREATION
    origin: ProjectOrigin = "agent"
    created_at: datetime
    updated_at: datetime


class SelectStrategyRequest(ContractModel):
    strategy_id: str = Field(min_length=1, max_length=128)


class AgentDecisionRequest(ContractModel):
    node_name: Literal[
        "director",
        "research",
        "production",
        "brand_packaging",
    ]
    action: Literal["approve", "retry"]
    feedback: str | None = Field(default=None, min_length=1, max_length=1000)
    strategy_id: str | None = Field(default=None, min_length=1, max_length=128)

    @model_validator(mode="after")
    def validate_strategy_decision(self) -> "AgentDecisionRequest":
        if self.node_name == "research" and self.action == "approve":
            if self.strategy_id is None:
                raise ValueError("strategy_id is required when approving research strategy")
        elif self.strategy_id is not None:
            raise ValueError("strategy_id is only allowed when approving research strategy")
        return self


class RetryProjectRequest(ContractModel):
    node: Literal["research", "strategy", "production"]
    reason: str = Field(min_length=1, max_length=1000)


class WorkflowStartResponse(ContractModel):
    project_id: str = Field(min_length=1, max_length=128)
    job_id: str = Field(min_length=1, max_length=128)
    status: Literal["pending"] = "pending"


class WorkflowCancelResponse(ContractModel):
    project_id: str = Field(min_length=1, max_length=128)
    status: Literal["cancelled"] = "cancelled"


class ProjectEventRead(ContractModel):
    id: int = Field(ge=1)
    project_id: str = Field(min_length=1, max_length=128)
    event_type: str = Field(min_length=1, max_length=100)
    node_name: str | None = Field(default=None, max_length=100)
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class ContentProjectResult(ContractModel):
    project_id: str = Field(min_length=1, max_length=128)
    status: ProjectStatus
    selected_strategy_id: str | None = None
    resolved_intent: TaskIntent = TaskIntent.FULL_CREATION
    strategy: dict[str, Any] = Field(default_factory=dict)
    copywriting: dict[str, Any] = Field(default_factory=dict)
    storyboard: dict[str, Any] = Field(default_factory=dict)
    video_prompt: dict[str, Any] = Field(default_factory=dict)
    brand_packaging: BrandPackagingOutput | None = None
    review: dict[str, Any] | None = None
    video_clone_analysis: dict[str, Any] = Field(default_factory=dict)
    video_clone_mapping: dict[str, Any] = Field(default_factory=dict)
    video_clone_prompt: dict[str, Any] = Field(default_factory=dict)
    video_clone_review: dict[str, Any] | None = None
    video_task: VideoTask | None = None
    providers: ResultProviders = Field(default_factory=ResultProviders)
