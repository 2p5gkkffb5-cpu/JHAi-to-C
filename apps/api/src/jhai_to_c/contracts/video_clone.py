from typing import Literal

from pydantic import Field, model_validator

from .common import ContractModel, ProjectReference
from .production import VideoPromptOutput


class VideoTechnicalProfile(ContractModel):
    duration_seconds: float = Field(gt=0, le=3600)
    width: int = Field(ge=1, le=16384)
    height: int = Field(ge=1, le=16384)
    fps: float = Field(gt=0, le=240)
    has_audio: bool
    sampled_frame_seconds: list[float] = Field(default_factory=list, max_length=12)


class VideoCloneShot(ContractModel):
    shot_id: str = Field(min_length=1, max_length=128)
    order: int = Field(ge=1, le=100)
    start_seconds: float = Field(ge=0, le=3600)
    end_seconds: float = Field(gt=0, le=3600)
    purpose: Literal["hook", "selling_point", "proof", "transition", "cta", "other"]
    visual_subject: str = Field(min_length=1, max_length=500)
    action: str = Field(min_length=1, max_length=1000)
    shot_size: str = Field(min_length=1, max_length=100)
    camera_movement: str = Field(min_length=1, max_length=200)
    dialogue_or_text: str = Field(default="", max_length=1000)
    transition: str = Field(default="", max_length=200)
    reusable_pattern: str = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def validate_timeline(self) -> "VideoCloneShot":
        if self.end_seconds <= self.start_seconds:
            raise ValueError("end_seconds must be greater than start_seconds")
        return self


class VideoCloneAnalysisOutput(ContractModel):
    analysis_basis: Literal[
        "mock_fixture",
        "ffmpeg_keyframes",
        "gemini_native_video",
    ]
    reference_id: str = Field(min_length=1, max_length=128)
    technical: VideoTechnicalProfile
    hook_summary: str = Field(min_length=1, max_length=1000)
    narrative_structure: list[str] = Field(min_length=1, max_length=20)
    pacing_summary: str = Field(min_length=1, max_length=1000)
    visual_style: str = Field(min_length=1, max_length=1000)
    audio_style: str = Field(min_length=1, max_length=1000)
    transferable_dna: list[str] = Field(min_length=1, max_length=20)
    protected_elements: list[str] = Field(default_factory=list, max_length=20)
    shots: list[VideoCloneShot] = Field(min_length=1, max_length=30)
    warnings: list[str] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def validate_shots(self) -> "VideoCloneAnalysisOutput":
        shot_ids = [shot.shot_id for shot in self.shots]
        if len(set(shot_ids)) != len(shot_ids):
            raise ValueError("video clone shot ids must be unique")
        if any(shot.end_seconds > self.technical.duration_seconds + 0.05 for shot in self.shots):
            raise ValueError("video clone shots must stay inside the source duration")
        return self


class VideoCloneMappingItem(ContractModel):
    shot_id: str = Field(min_length=1, max_length=128)
    replacement_reference_ids: list[str] = Field(min_length=1, max_length=10)
    retained_structure: list[str] = Field(default_factory=list, max_length=10)
    rewritten_subject: str = Field(min_length=1, max_length=500)
    rewritten_action: str = Field(min_length=1, max_length=1000)
    rewritten_dialogue_or_text: str = Field(default="", max_length=1000)
    compliance_changes: list[str] = Field(default_factory=list, max_length=10)


class VideoCloneMappingOutput(ContractModel):
    strategy: str = Field(min_length=1, max_length=1000)
    clone_level: Literal["结构借鉴", "平衡复刻", "高还原"]
    source_reference_id: str = Field(min_length=1, max_length=128)
    replacement_reference_ids: list[str] = Field(min_length=1, max_length=10)
    mappings: list[VideoCloneMappingItem] = Field(min_length=1, max_length=30)
    continuity_rules: list[str] = Field(min_length=1, max_length=20)
    compliance_notes: list[str] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def validate_mappings(self) -> "VideoCloneMappingOutput":
        shot_ids = [mapping.shot_id for mapping in self.mappings]
        if len(set(shot_ids)) != len(shot_ids):
            raise ValueError("video clone mapping shot ids must be unique")
        allowed = set(self.replacement_reference_ids)
        if any(set(mapping.replacement_reference_ids) - allowed for mapping in self.mappings):
            raise ValueError("mapping references must be declared in replacement_reference_ids")
        return self


class VideoCloneShotPrompt(ContractModel):
    shot_id: str = Field(min_length=1, max_length=128)
    prompt: str = Field(min_length=1, max_length=5000)
    negative_prompt: str = Field(default="", max_length=1000)
    reference_ids: list[str] = Field(min_length=1, max_length=10)


class VideoClonePromptOutput(ContractModel):
    optimization_summary: str = Field(min_length=1, max_length=1000)
    shot_prompts: list[VideoCloneShotPrompt] = Field(min_length=1, max_length=30)
    generation: VideoPromptOutput

    @model_validator(mode="after")
    def validate_prompts(self) -> "VideoClonePromptOutput":
        shot_ids = [shot.shot_id for shot in self.shot_prompts]
        if len(set(shot_ids)) != len(shot_ids):
            raise ValueError("video clone prompt shot ids must be unique")
        allowed = set(self.generation.reference_ids)
        if any(set(shot.reference_ids) - allowed for shot in self.shot_prompts):
            raise ValueError("shot prompt references must be declared in generation references")
        return self


class VideoCloneReviewCheck(ContractModel):
    name: str = Field(min_length=1, max_length=100)
    status: Literal["pass", "warning", "fail"]
    evidence: str = Field(min_length=1, max_length=1000)


class VideoCloneReviewOutput(ContractModel):
    status: Literal["pass", "warning", "fail"]
    score: int = Field(ge=0, le=100)
    analysis_basis: Literal[
        "mock_fixture",
        "ffmpeg_keyframes",
        "gemini_native_video",
    ]
    checks: list[VideoCloneReviewCheck] = Field(min_length=1, max_length=20)
    differences: list[str] = Field(default_factory=list, max_length=20)
    repair_suggestions: list[str] = Field(default_factory=list, max_length=20)


class VideoCloneAnalysisRequest(ContractModel):
    project_id: str = Field(min_length=1, max_length=128)
    request_text: str = Field(min_length=1, max_length=5000)
    reference: ProjectReference
    target_platform: str = Field(min_length=1, max_length=50)
    duration_seconds: int = Field(ge=5, le=180)
    aspect_ratio: Literal["9:16", "16:9", "1:1"]


class VideoCloneReviewRequest(ContractModel):
    project_id: str = Field(min_length=1, max_length=128)
    result_url: str = Field(min_length=1, max_length=5000)
    analysis: VideoCloneAnalysisOutput
    mapping: VideoCloneMappingOutput
    prompt: VideoClonePromptOutput
    replacement_references: list[ProjectReference] = Field(
        default_factory=list,
        max_length=10,
    )
