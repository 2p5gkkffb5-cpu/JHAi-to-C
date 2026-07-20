from __future__ import annotations

import asyncio
import base64
from pathlib import Path
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from jhai_to_c.db.models import UploadedAsset

_IMAGE_FORMATS = (
    ("image/png", ".png"),
    ("image/jpeg", ".jpg"),
    ("image/webp", ".webp"),
)
_VIDEO_FORMATS = (
    ("video/mp4", ".mp4"),
    ("video/quicktime", ".mov"),
    ("video/webm", ".webm"),
)


class AssetValidationError(ValueError):
    pass


class UploadedAssetService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        upload_dir: str | Path,
        *,
        max_bytes: int,
        max_video_bytes: int | None = None,
    ) -> None:
        self._session_factory = session_factory
        self.upload_dir = Path(upload_dir).expanduser().resolve()
        self.max_bytes = max_bytes
        self.max_video_bytes = max_video_bytes or max_bytes

    async def store_image(
        self,
        data: bytes,
        *,
        original_name: str,
        declared_content_type: str,
        owner_id: str | None,
    ) -> UploadedAsset:
        if not data:
            raise AssetValidationError("图片内容不能为空")
        if len(data) > self.max_bytes:
            raise AssetValidationError(f"图片不能超过 {self.max_bytes // (1024 * 1024)}MB")

        content_type, extension = _detect_image_type(data)
        normalized_declared_type = declared_content_type.partition(";")[0].strip().lower()
        if normalized_declared_type not in {item[0] for item in _IMAGE_FORMATS}:
            raise AssetValidationError("仅支持 JPEG、PNG 或 WebP 图片")
        if normalized_declared_type != content_type:
            raise AssetValidationError("图片内容与文件类型不一致")

        safe_name = _safe_original_name(original_name)
        asset_id = str(uuid4())
        storage_key = f"{asset_id}{extension}"
        destination = self.path_for(storage_key)
        temporary = destination.with_suffix(f"{destination.suffix}.tmp")

        await asyncio.to_thread(self.upload_dir.mkdir, parents=True, exist_ok=True)
        try:
            await asyncio.to_thread(temporary.write_bytes, data)
            await asyncio.to_thread(temporary.replace, destination)
            asset = UploadedAsset(
                id=asset_id,
                owner_id=owner_id,
                asset_type="image",
                original_name=safe_name,
                content_type=content_type,
                size_bytes=len(data),
                storage_key=storage_key,
            )
            async with self._session_factory.begin() as session:
                session.add(asset)
                await session.flush()
            return asset
        except Exception:
            await asyncio.to_thread(_unlink_if_exists, temporary)
            await asyncio.to_thread(_unlink_if_exists, destination)
            raise

    async def store_material(
        self,
        data: bytes,
        *,
        original_name: str,
        declared_content_type: str,
        owner_id: str | None,
    ) -> UploadedAsset:
        normalized_type = declared_content_type.partition(";")[0].strip().lower()
        if normalized_type in {item[0] for item in _IMAGE_FORMATS}:
            return await self.store_image(
                data,
                original_name=original_name,
                declared_content_type=declared_content_type,
                owner_id=owner_id,
            )
        if normalized_type not in {item[0] for item in _VIDEO_FORMATS}:
            raise AssetValidationError("仅支持 JPEG、PNG、WebP、MP4、MOV 或 WebM 素材")
        if not data:
            raise AssetValidationError("视频内容不能为空")
        if len(data) > self.max_video_bytes:
            raise AssetValidationError(
                f"视频不能超过 {self.max_video_bytes // (1024 * 1024)}MB"
            )

        content_type, extension = _detect_video_type(data, normalized_type)
        safe_name = _safe_original_name(original_name, fallback="未命名视频")
        asset_id = str(uuid4())
        storage_key = f"{asset_id}{extension}"
        destination = self.path_for(storage_key)
        temporary = destination.with_suffix(f"{destination.suffix}.tmp")

        await asyncio.to_thread(self.upload_dir.mkdir, parents=True, exist_ok=True)
        try:
            await asyncio.to_thread(temporary.write_bytes, data)
            await asyncio.to_thread(temporary.replace, destination)
            asset = UploadedAsset(
                id=asset_id,
                owner_id=owner_id,
                asset_type="video",
                original_name=safe_name,
                content_type=content_type,
                size_bytes=len(data),
                storage_key=storage_key,
            )
            async with self._session_factory.begin() as session:
                session.add(asset)
                await session.flush()
            return asset
        except Exception:
            await asyncio.to_thread(_unlink_if_exists, temporary)
            await asyncio.to_thread(_unlink_if_exists, destination)
            raise

    async def get(self, asset_id: str) -> UploadedAsset | None:
        async with self._session_factory() as session:
            return await session.get(UploadedAsset, asset_id)

    def path_for(self, storage_key: str) -> Path:
        path = (self.upload_dir / storage_key).resolve()
        if path.parent != self.upload_dir:
            raise ValueError("Invalid asset storage key")
        return path

    async def inline_image_data_url(self, asset_id: str) -> str | None:
        asset = await self.get(asset_id)
        if asset is None or asset.asset_type != "image":
            return None
        if asset.size_bytes > self.max_bytes:
            raise AssetValidationError("图片超过视频生成内联大小限制")
        path = self.path_for(asset.storage_key)
        if not path.is_file():
            raise AssetValidationError("图片素材文件不存在")
        data = await asyncio.to_thread(path.read_bytes)
        if len(data) != asset.size_bytes:
            raise AssetValidationError("图片素材文件大小与记录不一致")
        encoded = base64.b64encode(data).decode("ascii")
        return f"data:{asset.content_type};base64,{encoded}"


def _detect_image_type(data: bytes) -> tuple[str, str]:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png", ".png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg", ".jpg"
    if len(data) >= 12 and data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "image/webp", ".webp"
    raise AssetValidationError("文件不是有效的 JPEG、PNG 或 WebP 图片")


def _detect_video_type(data: bytes, declared_content_type: str) -> tuple[str, str]:
    if declared_content_type == "video/webm":
        if data.startswith(b"\x1a\x45\xdf\xa3"):
            return "video/webm", ".webm"
        raise AssetValidationError("文件不是有效的 WebM 视频")
    if len(data) >= 12 and data[4:8] == b"ftyp":
        extension = ".mov" if declared_content_type == "video/quicktime" else ".mp4"
        return declared_content_type, extension
    raise AssetValidationError("文件不是有效的 MP4 或 MOV 视频")


def _safe_original_name(value: str, *, fallback: str = "未命名图片") -> str:
    filename = Path(value.replace("\\", "/")).name.strip()
    filename = "".join(character for character in filename if character.isprintable())
    if not filename:
        return fallback
    return filename[:200]


def _unlink_if_exists(path: Path) -> None:
    path.unlink(missing_ok=True)
