from dataclasses import dataclass
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from jhai_to_c.contracts import (
    AccessConfigurationRead,
    AuthResponse,
    LoginRequest,
    PermissionDefinition,
    RegisterRequest,
    RolePermissionsUpdate,
    RoleRead,
    UserAccessUpdate,
    UserRead,
)
from jhai_to_c.db.models import User
from jhai_to_c.services import (
    PERMISSION_DEFINITIONS,
    PERMISSION_MANAGE_ACCESS,
    AccessConfigurationError,
    AuthPrincipal,
    AuthService,
    DuplicatePhoneError,
    InactiveUserError,
    InvalidCredentialsError,
    system_principal,
)

AUTH_COOKIE_NAME = "jinghu_session"
_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AuthIdentity:
    user: User | None
    principal: AuthPrincipal
    token: str | None


class AuthGuard:
    def __init__(self, service: AuthService, *, enabled: bool) -> None:
        self.service = service
        self.enabled = enabled

    async def optional_identity(
        self,
        request: Request,
        credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    ) -> AuthIdentity | None:
        if not self.enabled:
            return AuthIdentity(user=None, principal=system_principal(), token=None)
        token = (
            credentials.credentials
            if credentials is not None
            else request.cookies.get(AUTH_COOKIE_NAME)
        )
        if not token:
            return None
        authenticated = await self.service.authenticate(token)
        if authenticated is None:
            return None
        user, principal = authenticated
        return AuthIdentity(user=user, principal=principal, token=token)

    async def identity(
        self,
        request: Request,
        credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    ) -> AuthIdentity:
        identity = await self.optional_identity(request, credentials)
        if identity is None:
            raise _unauthorized()
        return identity

    def require(self, permission: str):
        identity_dependency = self.identity

        async def dependency(
            identity: Annotated[AuthIdentity, Depends(identity_dependency)],
        ) -> AuthPrincipal:
            if not identity.principal.has_permission(permission):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="当前账号没有执行此操作的权限",
                )
            return identity.principal

        return dependency


def build_auth_router(
    service: AuthService,
    guard: AuthGuard,
    *,
    cookie_secure: bool,
    session_days: int,
) -> APIRouter:
    router = APIRouter(prefix="/api", tags=["authentication"])

    @router.post(
        "/auth/register",
        response_model=AuthResponse,
        status_code=status.HTTP_201_CREATED,
    )
    async def register(data: RegisterRequest, response: Response) -> AuthResponse:
        try:
            result = await service.register(
                phone=data.phone,
                display_name=data.display_name,
                password=data.password,
            )
        except DuplicatePhoneError as exc:
            raise HTTPException(status_code=409, detail="该手机号已经注册") from exc
        _set_session_cookie(
            response,
            result.token,
            secure=cookie_secure,
            max_age=session_days * 24 * 60 * 60,
        )
        return AuthResponse(
            user=_user_read(result.user),
            access_token=result.token,
            expires_at=result.expires_at,
        )

    @router.post("/auth/login", response_model=AuthResponse)
    async def login(data: LoginRequest, response: Response) -> AuthResponse:
        try:
            result = await service.login(phone=data.phone, password=data.password)
        except InvalidCredentialsError as exc:
            raise HTTPException(status_code=401, detail="手机号或密码错误") from exc
        except InactiveUserError as exc:
            raise HTTPException(status_code=403, detail="账号已停用，请联系管理员") from exc
        _set_session_cookie(
            response,
            result.token,
            secure=cookie_secure,
            max_age=session_days * 24 * 60 * 60,
        )
        return AuthResponse(
            user=_user_read(result.user),
            access_token=result.token,
            expires_at=result.expires_at,
        )

    @router.get("/auth/me", response_model=UserRead | None)
    async def me(
        identity: Annotated[AuthIdentity | None, Depends(guard.optional_identity)],
    ) -> UserRead | None:
        if identity is None or identity.user is None:
            return None
        return _user_read(identity.user)

    @router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
    async def logout(
        response: Response,
        identity: Annotated[AuthIdentity, Depends(guard.identity)],
    ) -> None:
        if identity.token:
            await service.revoke(identity.token)
        response.delete_cookie(AUTH_COOKIE_NAME, path="/", samesite="lax")

    @router.get("/access", response_model=AccessConfigurationRead, tags=["access-control"])
    async def get_access_configuration(
        _: Annotated[AuthPrincipal, Depends(guard.require(PERMISSION_MANAGE_ACCESS))],
    ) -> AccessConfigurationRead:
        roles = await service.list_roles()
        users = await service.list_users()
        return AccessConfigurationRead(
            permissions=[
                PermissionDefinition(code=code, name=name, description=description)
                for code, name, description in PERMISSION_DEFINITIONS
            ],
            roles=[_role_read(role) for role in roles],
            users=[_user_read(user) for user in users],
        )

    @router.patch(
        "/access/roles/{role_id}",
        response_model=RoleRead,
        tags=["access-control"],
    )
    async def update_role_permissions(
        role_id: str,
        data: RolePermissionsUpdate,
        _: Annotated[AuthPrincipal, Depends(guard.require(PERMISSION_MANAGE_ACCESS))],
    ) -> RoleRead:
        try:
            role = await service.update_role_permissions(role_id, data.permissions)
        except AccessConfigurationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return _role_read(role)

    @router.patch(
        "/access/users/{user_id}",
        response_model=UserRead,
        tags=["access-control"],
    )
    async def update_user_access(
        user_id: str,
        data: UserAccessUpdate,
        _: Annotated[AuthPrincipal, Depends(guard.require(PERMISSION_MANAGE_ACCESS))],
    ) -> UserRead:
        try:
            user = await service.update_user_access(
                user_id,
                role_id=data.role_id,
                is_active=data.is_active,
            )
        except AccessConfigurationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return _user_read(user)

    return router


def _role_read(role) -> RoleRead:
    return RoleRead(
        id=role.id,
        code=role.code,
        name=role.name,
        description=role.description,
        permissions=list(role.permissions or []),
        is_system=role.is_system,
    )


def _user_read(user: User) -> UserRead:
    role = _role_read(user.role)
    return UserRead(
        id=user.id,
        phone=user.phone,
        display_name=user.display_name,
        role=role,
        permissions=list(role.permissions),
        is_active=user.is_active,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
    )


def _set_session_cookie(response: Response, token: str, *, secure: bool, max_age: int) -> None:
    response.set_cookie(
        AUTH_COOKIE_NAME,
        token,
        max_age=max_age,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
    )


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="请先登录",
        headers={"WWW-Authenticate": "Bearer"},
    )
