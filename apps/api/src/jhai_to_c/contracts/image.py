from enum import StrEnum
from typing import Annotated

from pydantic import Field

from .common import ContractModel


class ImageSize(StrEnum):
    SQUARE = "1024x1024"
    LANDSCAPE = "1536x1024"
    PORTRAIT = "1024x1536"


class ImageQuality(StrEnum):
    AUTO = "auto"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ImageGenerationRequest(ContractModel):
    prompt: str = Field(min_length=1, max_length=8_000)
    size: ImageSize = ImageSize.SQUARE
    quality: ImageQuality = ImageQuality.AUTO
    images: list[Annotated[str, Field(min_length=1, max_length=15_000_000)]] = Field(
        default_factory=list,
        max_length=10,
    )


class ImageGenerationResult(ContractModel):
    image_url: str = Field(min_length=1)
    revised_prompt: str | None = Field(default=None, max_length=8_000)
    provider: str = Field(min_length=1, max_length=100)
    model: str = Field(min_length=1, max_length=200)
    size: ImageSize
    quality: ImageQuality
