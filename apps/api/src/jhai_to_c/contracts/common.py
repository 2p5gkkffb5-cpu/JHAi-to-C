from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ContractModel(BaseModel):
    """Strict base model shared by every external and workflow contract."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ReferenceType(StrEnum):
    BRAND = "brand"
    PRODUCT = "product"
    IMAGE = "image"
    REFERENCE_VIDEO = "reference_video"
    BLUEPRINT = "blueprint"


class ProjectStatus(StrEnum):
    DRAFT = "draft"
    RUNNING = "running"
    WAITING_STRATEGY = "waiting_strategy"
    WAITING_APPROVAL = "waiting_approval"
    REVIEWING = "reviewing"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    NEEDS_ACTION = "needs_action"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ArtifactType(StrEnum):
    CREATIVE_BRIEF = "creative_brief"
    RESEARCH = "research"
    STRATEGY = "strategy"
    COPYWRITING = "copywriting"
    STORYBOARD = "storyboard"
    VIDEO_PROMPT = "video_prompt"
    REVIEW = "review"
    BRAND_PACKAGING = "brand_packaging"
    VIDEO_CLONE_ANALYSIS = "video_clone_analysis"
    VIDEO_CLONE_MAPPING = "video_clone_mapping"
    VIDEO_CLONE_PROMPT = "video_clone_prompt"
    VIDEO_CLONE_REVIEW = "video_clone_review"


class ProjectReference(ContractModel):
    type: ReferenceType
    id: str = Field(min_length=1, max_length=128)
    label: str = Field(min_length=1, max_length=200)
    snapshot: dict[str, Any] = Field(default_factory=dict)


class ContractError(ContractModel):
    code: str = Field(min_length=1, max_length=100)
    message: str = Field(min_length=1, max_length=1000)
    node: str | None = Field(default=None, max_length=100)
    details: dict[str, Any] = Field(default_factory=dict)


class TimestampedContract(ContractModel):
    created_at: datetime
    updated_at: datetime
