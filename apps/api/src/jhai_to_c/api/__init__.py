"""FastAPI routes for the Phase 1 backend."""

from .assets import build_assets_router
from .auth import AuthGuard, build_auth_router
from .content_projects import build_content_projects_router
from .images import build_images_router

__all__ = [
    "AuthGuard",
    "build_assets_router",
    "build_auth_router",
    "build_content_projects_router",
    "build_images_router",
]
