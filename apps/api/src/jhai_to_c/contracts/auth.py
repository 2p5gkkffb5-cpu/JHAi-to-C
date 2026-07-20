from __future__ import annotations

import re
from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator

_PHONE_PATTERN = re.compile(r"^\+?[1-9]\d{7,14}$")


def normalize_phone(value: str) -> str:
    normalized = re.sub(r"[\s-]", "", value.strip())
    if not _PHONE_PATTERN.fullmatch(normalized):
        raise ValueError("请输入有效的手机号（8-15 位数字，可带国家区号）")
    return normalized


class RegisterRequest(BaseModel):
    phone: str
    display_name: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=8, max_length=128)
    password_confirm: str = Field(min_length=8, max_length=128)

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        return normalize_phone(value)

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("昵称不能为空")
        return normalized

    @model_validator(mode="after")
    def passwords_match(self) -> RegisterRequest:
        if self.password != self.password_confirm:
            raise ValueError("两次输入的密码不一致")
        return self


class LoginRequest(BaseModel):
    phone: str
    password: str = Field(min_length=1, max_length=128)

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        return normalize_phone(value)


class PermissionDefinition(BaseModel):
    code: str
    name: str
    description: str


class RoleRead(BaseModel):
    id: str
    code: str
    name: str
    description: str
    permissions: list[str]
    is_system: bool


class UserRead(BaseModel):
    id: str
    phone: str
    display_name: str
    role: RoleRead
    permissions: list[str]
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None


class AuthResponse(BaseModel):
    user: UserRead
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime


class AccessConfigurationRead(BaseModel):
    permissions: list[PermissionDefinition]
    roles: list[RoleRead]
    users: list[UserRead]


class RolePermissionsUpdate(BaseModel):
    permissions: list[str] = Field(max_length=50)


class UserAccessUpdate(BaseModel):
    role_id: str | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def has_update(self) -> UserAccessUpdate:
        if self.role_id is None and self.is_active is None:
            raise ValueError("至少需要修改角色或账号状态")
        return self
