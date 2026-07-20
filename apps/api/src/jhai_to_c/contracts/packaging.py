from typing import Literal

from pydantic import Field

from .common import ContractModel


class BrandFoundation(ContractModel):
    brand_name: str = Field(min_length=1, max_length=200)
    positioning: str = Field(min_length=1, max_length=1000)
    target_audience: str = Field(min_length=1, max_length=1000)
    value_proposition: str = Field(min_length=1, max_length=1000)
    slogan: str = Field(min_length=1, max_length=300)
    personality: list[str] = Field(min_length=1, max_length=8)


class VisualSystem(ContractModel):
    creative_direction: str = Field(min_length=1, max_length=1500)
    primary_color: str = Field(min_length=1, max_length=100)
    secondary_colors: list[str] = Field(default_factory=list, max_length=6)
    typography: str = Field(min_length=1, max_length=500)
    photography_style: str = Field(min_length=1, max_length=1000)
    logo_direction: str = Field(min_length=1, max_length=1000)
    image_rules: list[str] = Field(min_length=1, max_length=12)


class PackagingAsset(ContractModel):
    asset_name: str = Field(min_length=1, max_length=200)
    channel: str = Field(min_length=1, max_length=100)
    purpose: str = Field(min_length=1, max_length=500)
    copy_text: str = Field(min_length=1, max_length=2000)
    image_brief: str = Field(min_length=1, max_length=2000)
    recommended_ratio: str = Field(min_length=1, max_length=50)


class ContentKit(ContractModel):
    brand_story: str = Field(min_length=1, max_length=3000)
    store_bio: str = Field(min_length=1, max_length=500)
    selling_points: list[str] = Field(min_length=1, max_length=12)
    tone_of_voice: list[str] = Field(min_length=1, max_length=8)
    reusable_headlines: list[str] = Field(min_length=1, max_length=12)


class RolloutStep(ContractModel):
    order: int = Field(ge=1, le=30)
    task: str = Field(min_length=1, max_length=500)
    deliverable: str = Field(min_length=1, max_length=500)
    priority: Literal["high", "medium", "low"]


class BrandPackagingOutput(ContractModel):
    """Complete store or brand packaging package produced in one validated call."""

    package_type: Literal["store", "brand"]
    executive_summary: str = Field(min_length=1, max_length=1500)
    brand_foundation: BrandFoundation
    visual_system: VisualSystem
    assets: list[PackagingAsset] = Field(min_length=1, max_length=20)
    content_kit: ContentKit
    rollout_plan: list[RolloutStep] = Field(min_length=1, max_length=20)
    reference_ids: list[str] = Field(default_factory=list, max_length=20)
    assumptions: list[str] = Field(default_factory=list, max_length=20)
