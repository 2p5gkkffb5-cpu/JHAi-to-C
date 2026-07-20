from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from jhai_to_c.api.auth import AuthGuard
from jhai_to_c.contracts.image import ImageGenerationRequest, ImageGenerationResult
from jhai_to_c.providers.interfaces import ImageProvider
from jhai_to_c.providers.real.image import RealImageProviderError
from jhai_to_c.services import PERMISSION_GENERATE_IMAGE, AuthPrincipal


def build_images_router(provider: ImageProvider | None, auth_guard: AuthGuard) -> APIRouter:
    router = APIRouter(prefix="/api/images", tags=["images"])

    @router.post(
        "/generations",
        response_model=ImageGenerationResult,
        status_code=status.HTTP_201_CREATED,
    )
    async def generate_image(
        data: ImageGenerationRequest,
        _: Annotated[AuthPrincipal, Depends(auth_guard.require(PERMISSION_GENERATE_IMAGE))],
    ) -> ImageGenerationResult:
        if provider is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="AI 图片服务尚未配置",
            )
        try:
            return await provider.generate(request=data)
        except RealImageProviderError as exc:
            response_status = (
                status.HTTP_504_GATEWAY_TIMEOUT
                if "timed out" in str(exc).lower()
                else status.HTTP_502_BAD_GATEWAY
            )
            raise HTTPException(
                status_code=response_status,
                detail=f"图片生成失败：{exc}",
            ) from exc

    return router
