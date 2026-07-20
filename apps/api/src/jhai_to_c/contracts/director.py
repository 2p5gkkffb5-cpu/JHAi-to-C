from typing import Literal

from pydantic import Field

from .common import ContractModel


class CreativeBrief(ContractModel):
    industry: str = Field(min_length=1, max_length=100)
    product: str = Field(min_length=1, max_length=200)
    platform: str = Field(min_length=1, max_length=50)
    goal: str = Field(min_length=1, max_length=200)
    target_audience: str = Field(min_length=1, max_length=500)
    content_direction: str = Field(min_length=1, max_length=500)
    duration_seconds: int = Field(ge=5, le=180)
    aspect_ratio: Literal["9:16", "16:9", "1:1"]
    tone: list[str] = Field(default_factory=list, max_length=10)
    must_include: list[str] = Field(default_factory=list, max_length=20)
    must_avoid: list[str] = Field(default_factory=list, max_length=20)


class DirectorOutput(ContractModel):
    workflow_type: Literal["topic_to_video", "brand_packaging"] = "topic_to_video"
    creative_brief: CreativeBrief
    missing_fields: list[str] = Field(default_factory=list, max_length=20)
    assumptions: list[str] = Field(default_factory=list, max_length=20)
