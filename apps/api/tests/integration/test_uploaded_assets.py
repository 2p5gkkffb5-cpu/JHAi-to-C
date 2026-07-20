import base64

import pytest
from httpx import ASGITransport, AsyncClient

from jhai_to_c.config import Settings
from jhai_to_c.main import create_app

_ONE_PIXEL_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)
_MINIMAL_MP4 = b"\x00\x00\x00\x18ftypisom\x00\x00\x02\x00isomiso2"


def _settings(tmp_path, *, asset_max_bytes: int = 10 * 1024 * 1024) -> Settings:
    return Settings(
        _env_file=None,
        app_env="test",
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'assets.db'}",
        langgraph_checkpoint_path=str(tmp_path / "asset-checkpoints.db"),
        asset_upload_dir=str(tmp_path / "uploads"),
        asset_max_bytes=asset_max_bytes,
        mock_provider_latency_ms=0,
    )


@pytest.mark.asyncio
async def test_uploaded_image_can_be_persisted_as_a_project_reference(tmp_path) -> None:
    app = create_app(_settings(tmp_path))

    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            upload_response = await client.post(
                "/api/assets/images",
                params={"filename": "产品参考图.png"},
                content=_ONE_PIXEL_PNG,
                headers={"Content-Type": "image/png"},
            )
            assert upload_response.status_code == 201, upload_response.text
            uploaded = upload_response.json()
            assert uploaded["content_type"] == "image/png"
            assert uploaded["reference"] == {
                "type": "image",
                "id": uploaded["id"],
                "label": "@产品参考图.png",
                "snapshot": {
                    "url": uploaded["url"],
                    "filename": "产品参考图.png",
                    "content_type": "image/png",
                    "size_bytes": len(_ONE_PIXEL_PNG),
                },
            }

            image_response = await client.get(f"/api/assets/{uploaded['id']}/content")
            assert image_response.status_code == 200
            assert image_response.headers["content-type"] == "image/png"
            assert image_response.content == _ONE_PIXEL_PNG

            inline_url = await app.state.asset_service.inline_image_data_url(
                uploaded["id"]
            )
            assert inline_url == (
                "data:image/png;base64," + base64.b64encode(_ONE_PIXEL_PNG).decode()
            )

            project_response = await client.post(
                "/api/content-projects",
                json={
                    "title": "引用上传图片",
                    "request_text": "参考这张产品图制作一条短视频",
                    "references": [uploaded["reference"]],
                },
            )
            assert project_response.status_code == 201, project_response.text
            assert project_response.json()["references"] == [uploaded["reference"]]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("content_type", "content", "expected_detail"),
    [
        ("text/plain", _ONE_PIXEL_PNG, "仅支持 JPEG、PNG 或 WebP 图片"),
        ("image/png", b"not-an-image", "文件不是有效的 JPEG、PNG 或 WebP 图片"),
    ],
)
async def test_uploaded_image_rejects_invalid_content(
    tmp_path,
    content_type: str,
    content: bytes,
    expected_detail: str,
) -> None:
    app = create_app(_settings(tmp_path))

    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/assets/images",
                params={"filename": "bad.png"},
                content=content,
                headers={"Content-Type": content_type},
            )

    assert response.status_code == 422
    assert response.json()["detail"] == expected_detail


@pytest.mark.asyncio
async def test_uploaded_image_enforces_size_limit(tmp_path) -> None:
    app = create_app(_settings(tmp_path, asset_max_bytes=1024 * 1024))

    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/assets/images",
                params={"filename": "large.png"},
                content=_ONE_PIXEL_PNG + b"0" * (1024 * 1024),
                headers={"Content-Type": "image/png"},
            )

    assert response.status_code == 413
    assert response.json()["detail"] == "图片不能超过 1MB"


@pytest.mark.asyncio
async def test_uploaded_video_material_can_be_referenced_by_a_video_project(tmp_path) -> None:
    app = create_app(_settings(tmp_path))

    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            upload_response = await client.post(
                "/api/assets/materials",
                params={"filename": "参考运镜.mp4"},
                content=_MINIMAL_MP4,
                headers={"Content-Type": "video/mp4"},
            )
            assert upload_response.status_code == 201, upload_response.text
            uploaded = upload_response.json()
            assert uploaded["asset_type"] == "video"
            assert uploaded["reference"]["type"] == "reference_video"
            assert uploaded["reference"]["label"] == "@参考运镜.mp4"

            content_response = await client.get(f"/api/assets/{uploaded['id']}/content")
            assert content_response.status_code == 200
            assert content_response.headers["content-type"] == "video/mp4"
            assert content_response.content == _MINIMAL_MP4

            project_response = await client.post(
                "/api/content-projects",
                json={
                    "title": "引用视频素材",
                    "request_text": "参考 @参考运镜.mp4 生成一条短片",
                    "references": [uploaded["reference"]],
                    "requested_mode": "video_generation",
                },
            )
            assert project_response.status_code == 201, project_response.text
            project = project_response.json()
            assert project["references"] == [uploaded["reference"]]

            history_response = await client.get("/api/content-projects")
            assert history_response.status_code == 200
            assert history_response.json()[0]["requested_mode"] == "video_generation"
