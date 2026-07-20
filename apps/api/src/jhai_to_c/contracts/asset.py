from typing import Literal

from pydantic import Field

from .common import ContractModel, ProjectReference


class UploadedImageRead(ContractModel):
    id: str = Field(min_length=1, max_length=128)
    filename: str = Field(min_length=1, max_length=200)
    content_type: str = Field(min_length=1, max_length=100)
    size_bytes: int = Field(gt=0)
    url: str = Field(min_length=1, max_length=2000)
    reference: ProjectReference


class UploadedMaterialRead(ContractModel):
    id: str = Field(min_length=1, max_length=128)
    asset_type: Literal["image", "video"]
    filename: str = Field(min_length=1, max_length=200)
    content_type: str = Field(min_length=1, max_length=100)
    size_bytes: int = Field(gt=0)
    url: str = Field(min_length=1, max_length=2000)
    reference: ProjectReference
