import json

import httpx
import pytest

from jhai_to_c.contracts.image import ImageGenerationRequest
from jhai_to_c.providers.real.image import RealImageProvider, RealImageProviderError


def _request(**overrides: object) -> ImageGenerationRequest:
    payload = {
        "prompt": "暖黄色灯光下的雨夜咖啡店，真实摄影",
        "size": "1536x1024",
        "quality": "high",
    }
    payload.update(overrides)
    return ImageGenerationRequest.model_validate(payload)


@pytest.mark.asyncio
async def test_generate_uses_grs_image_endpoint() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url == "https://image.example.test/v1/api/generate"
        assert request.headers["Authorization"] == "Bearer image-secret"
        assert request.extensions["timeout"]["read"] == 42
        assert json.loads(request.content) == {
            "model": "gpt-image-2-vip",
            "prompt": "暖黄色灯光下的雨夜咖啡店，真实摄影",
            "images": [],
            "aspectRatio": "1536x1024",
            "replyType": "json",
        }
        return httpx.Response(
            200,
            json={
                "id": "task-1",
                "status": "succeeded",
                "results": [{"url": "https://cdn.example.test/generated.png"}],
                "progress": 100,
                "error": "",
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = RealImageProvider(
            api_key="image-secret",
            base_url="https://image.example.test/v1/",
            model="gpt-image-2-vip",
            request_timeout_seconds=42,
            client=client,
        )
        result = await provider.generate(request=_request())

    assert result.image_url == "https://cdn.example.test/generated.png"
    assert result.revised_prompt is None
    assert result.provider == "grsai"
    assert result.model == "gpt-image-2-vip"


@pytest.mark.asyncio
async def test_generate_passes_reference_images() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert json.loads(request.content)["images"] == [
            "https://cdn.example.test/reference.jpg",
            "data:image/png;base64,aW1hZ2U=",
        ]
        return httpx.Response(
            200,
            json={
                "status": "succeeded",
                "results": [{"url": "https://cdn.example.test/edited.png"}],
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = RealImageProvider(
            api_key="image-secret",
            base_url="https://image.example.test/v1",
            model="gpt-image-2-vip",
            client=client,
        )
        result = await provider.generate(
            request=_request(
                images=[
                    "https://cdn.example.test/reference.jpg",
                    "data:image/png;base64,aW1hZ2U=",
                ]
            )
        )

    assert result.image_url == "https://cdn.example.test/edited.png"


@pytest.mark.asyncio
async def test_generate_rejects_missing_image_payload() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": "succeeded", "results": [{}]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = RealImageProvider(
            api_key="image-secret",
            base_url="https://image.example.test/v1",
            model="gpt-image-2-vip",
            client=client,
        )
        with pytest.raises(RealImageProviderError, match=r"results\[0\].url"):
            await provider.generate(request=_request())


@pytest.mark.asyncio
async def test_generate_rejects_failed_task_status() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"id": "task-1", "status": "failed", "results": [], "error": "内容审核未通过"},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = RealImageProvider(
            api_key="image-secret",
            base_url="https://image.example.test/v1",
            model="gpt-image-2-vip",
            client=client,
        )
        with pytest.raises(RealImageProviderError, match="内容审核未通过"):
            await provider.generate(request=_request())


@pytest.mark.asyncio
async def test_generate_http_error_never_exposes_secret() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": {"message": "insufficient credits"}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = RealImageProvider(
            api_key="image-secret",
            base_url="https://image.example.test/v1",
            model="gpt-image-2-vip",
            client=client,
        )
        with pytest.raises(RealImageProviderError) as caught:
            await provider.generate(request=_request())

    assert caught.value.status_code == 429
    assert "insufficient credits" in str(caught.value)
    assert "image-secret" not in str(caught.value)
