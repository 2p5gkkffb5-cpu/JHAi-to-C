from enum import StrEnum
from typing import Literal

from pydantic import Field

from .common import ContractModel, ProjectReference


class RequestedMode(StrEnum):
    AUTO = "auto"
    FULL_CREATION = "full_creation"
    VIDEO_GENERATION = "video_generation"
    IMAGE_GENERATION = "image_generation"
    BRAND_PACKAGING = "brand_packaging"
    VIDEO_CLONE = "video_clone"


class TaskIntent(StrEnum):
    FULL_CREATION = "full_creation"
    VIDEO_GENERATION = "video_generation"
    IMAGE_GENERATION = "image_generation"
    BRAND_PACKAGING = "brand_packaging"
    VIDEO_CLONE = "video_clone"


class IntentRoutingInput(ContractModel):
    request_text: str = Field(min_length=1, max_length=5000)
    references: list[ProjectReference] = Field(default_factory=list, max_length=20)
    requested_mode: RequestedMode = RequestedMode.FULL_CREATION


class IntentDecision(ContractModel):
    intent: TaskIntent
    confidence: float = Field(ge=0, le=1)
    reason_code: Literal[
        "explicit_mode",
        "full_workflow_requested",
        "video_output_requested",
        "image_output_requested",
        "ambiguous_default",
    ]
