from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import FileResponse

from jhai_to_c.api.auth import AuthGuard
from jhai_to_c.contracts import UploadedImageRead, UploadedMaterialRead
from jhai_to_c.contracts.common import ProjectReference, ReferenceType
from jhai_to_c.services import (
    PERMISSION_UPLOAD_ASSET,
    AssetValidationError,
    AuthPrincipal,
    UploadedAssetService,
)


def build_assets_router(
    service: UploadedAssetService,
    auth_guard: AuthGuard,
    *,
    public_base_url: str | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/api/assets", tags=["assets"])
    upload_permission = Depends(auth_guard.require(PERMISSION_UPLOAD_ASSET))

    @router.post(
        "/images",
        response_model=UploadedImageRead,
        status_code=status.HTTP_201_CREATED,
    )
    async def upload_image(
        request: Request,
        principal: AuthPrincipal = upload_permission,
        filename: str = Query(min_length=1, max_length=200),
    ) -> UploadedImageRead:
        content_length = request.headers.get("content-length")
        if content_length and content_length.isdigit() and int(content_length) > service.max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail=f"图片不能超过 {service.max_bytes // (1024 * 1024)}MB",
            )

        data = bytearray()
        async for chunk in request.stream():
            data.extend(chunk)
            if len(data) > service.max_bytes:
                raise HTTPException(
                    status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                    detail=f"图片不能超过 {service.max_bytes // (1024 * 1024)}MB",
                )

        try:
            asset = await service.store_image(
                bytes(data),
                original_name=filename,
                declared_content_type=request.headers.get("content-type", ""),
                owner_id=principal.user_id,
            )
        except AssetValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=str(exc),
            ) from exc

        path = f"/api/assets/{asset.id}/content"
        url = (
            f"{public_base_url.rstrip('/')}{path}"
            if public_base_url
            else str(request.url_for("get_uploaded_asset_content", asset_id=asset.id))
        )
        reference = ProjectReference(
            type=ReferenceType.IMAGE,
            id=asset.id,
            label=f"@{asset.original_name}",
            snapshot={
                "url": url,
                "filename": asset.original_name,
                "content_type": asset.content_type,
                "size_bytes": asset.size_bytes,
            },
        )
        return UploadedImageRead(
            id=asset.id,
            filename=asset.original_name,
            content_type=asset.content_type,
            size_bytes=asset.size_bytes,
            url=url,
            reference=reference,
        )

    @router.post(
        "/materials",
        response_model=UploadedMaterialRead,
        status_code=status.HTTP_201_CREATED,
    )
    async def upload_material(
        request: Request,
        principal: AuthPrincipal = upload_permission,
        filename: str = Query(min_length=1, max_length=200),
    ) -> UploadedMaterialRead:
        declared_type = request.headers.get("content-type", "").partition(";")[0].lower()
        is_video = declared_type.startswith("video/")
        max_bytes = service.max_video_bytes if is_video else service.max_bytes
        content_length = request.headers.get("content-length")
        if content_length and content_length.isdigit() and int(content_length) > max_bytes:
            kind = "视频" if is_video else "图片"
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail=f"{kind}不能超过 {max_bytes // (1024 * 1024)}MB",
            )

        data = bytearray()
        async for chunk in request.stream():
            data.extend(chunk)
            if len(data) > max_bytes:
                kind = "视频" if is_video else "图片"
                raise HTTPException(
                    status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                    detail=f"{kind}不能超过 {max_bytes // (1024 * 1024)}MB",
                )

        try:
            asset = await service.store_material(
                bytes(data),
                original_name=filename,
                declared_content_type=request.headers.get("content-type", ""),
                owner_id=principal.user_id,
            )
        except AssetValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=str(exc),
            ) from exc

        path = f"/api/assets/{asset.id}/content"
        url = (
            f"{public_base_url.rstrip('/')}{path}"
            if public_base_url
            else str(request.url_for("get_uploaded_asset_content", asset_id=asset.id))
        )
        reference_type = (
            ReferenceType.IMAGE
            if asset.asset_type == "image"
            else ReferenceType.REFERENCE_VIDEO
        )
        reference = ProjectReference(
            type=reference_type,
            id=asset.id,
            label=f"@{asset.original_name}",
            snapshot={
                "url": url,
                "filename": asset.original_name,
                "content_type": asset.content_type,
                "size_bytes": asset.size_bytes,
            },
        )
        return UploadedMaterialRead(
            id=asset.id,
            asset_type=asset.asset_type,
            filename=asset.original_name,
            content_type=asset.content_type,
            size_bytes=asset.size_bytes,
            url=url,
            reference=reference,
        )

    @router.get(
        "/{asset_id}/content",
        name="get_uploaded_asset_content",
        response_class=FileResponse,
    )
    async def get_uploaded_asset_content(asset_id: str) -> FileResponse:
        asset = await service.get(asset_id)
        if asset is None or asset.asset_type not in {"image", "video"}:
            raise HTTPException(status_code=404, detail="素材不存在")
        path = service.path_for(asset.storage_key)
        if not path.is_file():
            raise HTTPException(status_code=404, detail="素材文件不存在")
        return FileResponse(
            path,
            media_type=asset.content_type,
            filename=asset.original_name,
            content_disposition_type="inline",
            headers={
                "Cache-Control": "public, max-age=31536000, immutable",
                "X-Content-Type-Options": "nosniff",
            },
        )

    return router
