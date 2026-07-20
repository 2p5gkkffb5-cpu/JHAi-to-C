from datetime import datetime
from typing import Any, Literal

from pydantic import ConfigDict, Field, model_validator

from .common import ContractModel

StudioModule = Literal["ai_video", "ai_image", "canvas", "asset"]
StudioResourceStatus = Literal["draft", "ready", "archived"]


class StudioModuleRead(ContractModel):
    module: StudioModule
    slug: str
    label: str
    description: str


class StudioResourceCreate(ContractModel):
    title: str = Field(min_length=1, max_length=200)
    content: dict[str, Any] = Field(default_factory=dict)
    status: StudioResourceStatus = "draft"
    actor: str = Field(default="anonymous", min_length=1, max_length=100)


class StudioResourceUpdate(ContractModel):
    expected_revision: int = Field(ge=1)
    title: str | None = Field(default=None, min_length=1, max_length=200)
    content: dict[str, Any] | None = None
    status: StudioResourceStatus | None = None
    actor: str = Field(default="anonymous", min_length=1, max_length=100)
    change_note: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def reject_explicit_null_updates(self) -> "StudioResourceUpdate":
        for field_name in ("title", "content", "status"):
            if field_name in self.model_fields_set and getattr(self, field_name) is None:
                raise ValueError(f"{field_name} cannot be null")
        return self


class StudioResourceRead(ContractModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid", str_strip_whitespace=True)

    id: str
    module: StudioModule
    title: str
    content: dict[str, Any]
    status: StudioResourceStatus
    revision: int
    created_by: str
    updated_by: str
    created_at: datetime
    updated_at: datetime


class StudioRevisionRead(ContractModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid", str_strip_whitespace=True)

    id: int
    resource_id: str
    revision: int
    title: str
    content: dict[str, Any]
    status: StudioResourceStatus
    actor: str
    change_note: str | None = None
    created_at: datetime


class StudioResourceDuplicate(ContractModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    actor: str = Field(default="anonymous", min_length=1, max_length=100)
