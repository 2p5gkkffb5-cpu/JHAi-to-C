from typing import Literal

from pydantic import Field

from .common import ContractModel


class ProductionCoordinatorOutput(ContractModel):
    production_goal: str = Field(min_length=1, max_length=500)
    copywriting_instruction: str = Field(min_length=1, max_length=1000)
    storyboard_instruction: str = Field(min_length=1, max_length=1000)
    video_prompt_instruction: str = Field(min_length=1, max_length=1000)
    continuity_rules: list[str] = Field(default_factory=list, max_length=20)
    allowed_reference_ids: list[str] = Field(default_factory=list, max_length=20)


class OnscreenText(ContractModel):
    start_seconds: float = Field(ge=0, le=180)
    end_seconds: float = Field(gt=0, le=180)
    text: str = Field(min_length=1, max_length=200)


class FactBinding(ContractModel):
    field: str = Field(min_length=1, max_length=100)
    reference_id: str = Field(min_length=1, max_length=128)


class CopywritingOutput(ContractModel):
    title: str = Field(min_length=1, max_length=200)
    hook: str = Field(min_length=1, max_length=500)
    voiceover: str = Field(min_length=1, max_length=5000)
    onscreen_text: list[OnscreenText] = Field(default_factory=list, max_length=30)
    cta: str = Field(min_length=1, max_length=500)
    estimated_duration_seconds: int = Field(ge=5, le=180)
    tone: str = Field(min_length=1, max_length=200)
    fact_bindings: list[FactBinding] = Field(default_factory=list, max_length=30)


class CameraSpec(ContractModel):
    shot_size: str = Field(min_length=1, max_length=100)
    angle: str = Field(min_length=1, max_length=100)
    movement: str = Field(min_length=1, max_length=200)


class StoryboardShot(ContractModel):
    shot_id: str = Field(min_length=1, max_length=128)
    order: int = Field(ge=1, le=100)
    start_seconds: float = Field(ge=0, le=180)
    end_seconds: float = Field(gt=0, le=180)
    duration_seconds: float = Field(gt=0, le=60)
    purpose: Literal["hook", "selling_point", "proof", "transition", "cta", "other"]
    visual: str = Field(min_length=1, max_length=2000)
    subject: str = Field(min_length=1, max_length=500)
    action: str = Field(min_length=1, max_length=1000)
    camera: CameraSpec
    voiceover: str = Field(default="", max_length=1000)
    onscreen_text: str = Field(default="", max_length=300)
    transition: str = Field(default="", max_length=200)
    reference_ids: list[str] = Field(default_factory=list, max_length=10)
    generation_prompt: str = Field(min_length=1, max_length=5000)


class StoryboardOutput(ContractModel):
    total_duration_seconds: int = Field(ge=5, le=180)
    visual_style: str = Field(min_length=1, max_length=1000)
    continuity_rules: list[str] = Field(default_factory=list, max_length=20)
    shots: list[StoryboardShot] = Field(min_length=1, max_length=30)


class VideoPromptOutput(ContractModel):
    prompt: str = Field(min_length=1, max_length=10_000)
    negative_prompt: str = Field(default="", max_length=3000)
    duration_seconds: int = Field(ge=5, le=180)
    aspect_ratio: Literal["9:16", "16:9", "1:1"]
    reference_ids: list[str] = Field(default_factory=list, max_length=10)
    provider_parameters: dict[str, str | int | float | bool] = Field(default_factory=dict)


class ProductionPackageOutput(ContractModel):
    """Complete, internally consistent production package generated in one call."""

    production_plan: ProductionCoordinatorOutput
    copywriting: CopywritingOutput
    storyboard: StoryboardOutput
    video_prompt: VideoPromptOutput
