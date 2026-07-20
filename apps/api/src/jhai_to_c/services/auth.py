from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from jhai_to_c.db.base import utc_now
from jhai_to_c.db.models import AuthSession, Role, User

PERMISSION_CREATE_PROJECT = "content_projects:create"
PERMISSION_READ_PROJECT = "content_projects:read"
PERMISSION_READ_ALL_PROJECTS = "content_projects:read_all"
PERMISSION_UPDATE_PROJECT = "content_projects:update"
PERMISSION_CANCEL_PROJECT = "content_projects:cancel"
PERMISSION_GENERATE_IMAGE = "images:generate"
PERMISSION_UPLOAD_ASSET = "assets:upload"
PERMISSION_MANAGE_ACCESS = "access:manage"

PERMISSION_DEFINITIONS = (
    (PERMISSION_CREATE_PROJECT, "创建内容项目", "创建并启动新的 Agent 创作任务"),
    (PERMISSION_READ_PROJECT, "查看本人项目", "查看本人创建的项目、事件与交付结果"),
    (PERMISSION_READ_ALL_PROJECTS, "查看全部项目", "查看所有用户的内容项目"),
    (PERMISSION_UPDATE_PROJECT, "推进内容项目", "确认方案、重试并推进工作流"),
    (PERMISSION_CANCEL_PROJECT, "取消内容项目", "终止本人可访问的执行任务"),
    (PERMISSION_GENERATE_IMAGE, "生成图片", "调用 AI 图片生成能力"),
    (PERMISSION_UPLOAD_ASSET, "上传参考图片", "上传并在内容项目中引用图片"),
    (PERMISSION_MANAGE_ACCESS, "配置账号权限", "分配角色、停用账号并编辑角色权限"),
)
KNOWN_PERMISSIONS = frozenset(item[0] for item in PERMISSION_DEFINITIONS)
MEMBER_PERMISSIONS = [
    PERMISSION_CREATE_PROJECT,
    PERMISSION_READ_PROJECT,
    PERMISSION_UPDATE_PROJECT,
    PERMISSION_CANCEL_PROJECT,
    PERMISSION_GENERATE_IMAGE,
    PERMISSION_UPLOAD_ASSET,
]

ADMIN_ROLE_ID = "00000000-0000-0000-0000-000000000001"
MEMBER_ROLE_ID = "00000000-0000-0000-0000-000000000002"


class DuplicatePhoneError(ValueError):
    pass


class InvalidCredentialsError(ValueError):
    pass


class InactiveUserError(PermissionError):
    pass


class AccessConfigurationError(ValueError):
    pass


@dataclass(frozen=True)
class AuthPrincipal:
    user_id: str | None
    phone: str
    display_name: str
    role_code: str
    permissions: frozenset[str]
    is_system: bool = False

    def has_permission(self, permission: str) -> bool:
        return self.is_system or "*" in self.permissions or permission in self.permissions


@dataclass(frozen=True)
class AuthResult:
    user: User
    token: str
    expires_at: object


class AuthService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        session_days: int = 30,
    ) -> None:
        self._session_factory = session_factory
        self._session_days = session_days

    async def ensure_default_roles(self) -> None:
        defaults = (
            Role(
                id=ADMIN_ROLE_ID,
                code="admin",
                name="管理员",
                description="拥有全部功能和权限配置能力",
                permissions=["*"],
                is_system=True,
            ),
            Role(
                id=MEMBER_ROLE_ID,
                code="member",
                name="成员",
                description="可使用日常创作能力，仅访问本人项目",
                permissions=list(MEMBER_PERMISSIONS),
                is_system=True,
            ),
        )
        async with self._session_factory.begin() as session:
            existing = set(
                (
                    await session.scalars(
                        select(Role.code).where(Role.code.in_(["admin", "member"]))
                    )
                ).all()
            )
            session.add_all([role for role in defaults if role.code not in existing])

    async def register(
        self,
        *,
        phone: str,
        display_name: str,
        password: str,
    ) -> AuthResult:
        try:
            async with self._session_factory.begin() as session:
                existing = await session.scalar(select(User.id).where(User.phone == phone))
                if existing is not None:
                    raise DuplicatePhoneError(phone)

                user_count = await session.scalar(select(func.count(User.id))) or 0
                role_code = "admin" if user_count == 0 else "member"
                role = (
                    await session.execute(select(Role).where(Role.code == role_code))
                ).scalar_one()
                user = User(
                    phone=phone,
                    display_name=display_name,
                    password_hash=_hash_password(password),
                    role_id=role.id,
                    role=role,
                )
                session.add(user)
                await session.flush()
                token, auth_session = self._new_session(user.id)
                session.add(auth_session)
                await session.flush()
            return AuthResult(user=user, token=token, expires_at=auth_session.expires_at)
        except IntegrityError as exc:
            raise DuplicatePhoneError(phone) from exc

    async def login(self, *, phone: str, password: str) -> AuthResult:
        async with self._session_factory.begin() as session:
            statement = select(User).where(User.phone == phone).options(selectinload(User.role))
            user = (await session.execute(statement)).scalar_one_or_none()
            if user is None or not _verify_password(password, user.password_hash):
                raise InvalidCredentialsError(phone)
            if not user.is_active:
                raise InactiveUserError(phone)
            user.last_login_at = utc_now()
            token, auth_session = self._new_session(user.id)
            session.add(auth_session)
            await session.flush()
        return AuthResult(user=user, token=token, expires_at=auth_session.expires_at)

    async def authenticate(self, token: str) -> tuple[User, AuthPrincipal] | None:
        token_hash = _hash_token(token)
        statement = (
            select(AuthSession)
            .where(
                AuthSession.token_hash == token_hash,
                AuthSession.revoked_at.is_(None),
                AuthSession.expires_at > utc_now(),
            )
            .options(selectinload(AuthSession.user).selectinload(User.role))
        )
        async with self._session_factory() as session:
            auth_session = (await session.execute(statement)).scalar_one_or_none()
            if auth_session is None or not auth_session.user.is_active:
                return None
            user = auth_session.user
            permissions = frozenset(user.role.permissions or [])
            principal = AuthPrincipal(
                user_id=user.id,
                phone=user.phone,
                display_name=user.display_name,
                role_code=user.role.code,
                permissions=permissions,
            )
            return user, principal

    async def revoke(self, token: str) -> None:
        async with self._session_factory.begin() as session:
            await session.execute(
                update(AuthSession)
                .where(AuthSession.token_hash == _hash_token(token))
                .values(revoked_at=utc_now())
            )

    async def list_roles(self) -> list[Role]:
        async with self._session_factory() as session:
            return list((await session.scalars(select(Role).order_by(Role.code))).all())

    async def list_users(self) -> list[User]:
        statement = select(User).options(selectinload(User.role)).order_by(User.created_at, User.id)
        async with self._session_factory() as session:
            return list((await session.scalars(statement)).all())

    async def update_role_permissions(self, role_id: str, permissions: list[str]) -> Role:
        unknown = set(permissions) - KNOWN_PERMISSIONS
        if unknown:
            raise AccessConfigurationError(f"未知权限：{', '.join(sorted(unknown))}")
        async with self._session_factory.begin() as session:
            role = await session.get(Role, role_id)
            if role is None:
                raise AccessConfigurationError("角色不存在")
            if role.code == "admin":
                raise AccessConfigurationError("管理员角色固定拥有全部权限")
            role.permissions = sorted(set(permissions))
            await session.flush()
        return role

    async def update_user_access(
        self,
        user_id: str,
        *,
        role_id: str | None,
        is_active: bool | None,
    ) -> User:
        async with self._session_factory.begin() as session:
            statement = select(User).where(User.id == user_id).options(selectinload(User.role))
            user = (await session.execute(statement)).scalar_one_or_none()
            if user is None:
                raise AccessConfigurationError("用户不存在")

            next_role = user.role
            if role_id is not None and role_id != user.role_id:
                candidate = await session.get(Role, role_id)
                if candidate is None:
                    raise AccessConfigurationError("角色不存在")
                next_role = candidate

            removes_admin = user.role.code == "admin" and (
                next_role.code != "admin" or is_active is False
            )
            if removes_admin:
                active_admin_count = await session.scalar(
                    select(func.count(User.id))
                    .join(Role)
                    .where(Role.code == "admin", User.is_active.is_(True))
                )
                if (active_admin_count or 0) <= 1:
                    raise AccessConfigurationError("必须保留至少一个启用中的管理员")

            user.role_id = next_role.id
            user.role = next_role
            if is_active is not None:
                user.is_active = is_active
            if is_active is False:
                await session.execute(
                    update(AuthSession)
                    .where(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None))
                    .values(revoked_at=utc_now())
                )
            await session.flush()
        return user

    def _new_session(self, user_id: str) -> tuple[str, AuthSession]:
        token = secrets.token_urlsafe(32)
        expires_at = utc_now() + timedelta(days=self._session_days)
        return token, AuthSession(
            user_id=user_id,
            token_hash=_hash_token(token),
            expires_at=expires_at,
        )


def system_principal() -> AuthPrincipal:
    return AuthPrincipal(
        user_id=None,
        phone="",
        display_name="System",
        role_code="system",
        permissions=frozenset({"*"}),
        is_system=True,
    )


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return "$".join(
        (
            "scrypt",
            "16384",
            "8",
            "1",
            base64.urlsafe_b64encode(salt).decode("ascii"),
            base64.urlsafe_b64encode(digest).decode("ascii"),
        )
    )


def _verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, n, r, p, salt_text, digest_text = encoded.split("$")
        if algorithm != "scrypt":
            return False
        salt = base64.urlsafe_b64decode(salt_text.encode("ascii"))
        expected = base64.urlsafe_b64decode(digest_text.encode("ascii"))
        actual = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(expected),
        )
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False
