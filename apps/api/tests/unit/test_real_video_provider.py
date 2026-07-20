import json

import httpx
import pytest

from jhai_to_c.contracts.video import (
    VideoGenerationRequest,
    VideoTaskStatus,
)
from jhai_to_c.providers.real.video import (
    RealVideoProvider,
    RealVideoProviderError,
)


def _video_request(**overrides: object) -> VideoGenerationRequest:
    payload = {
        "project_id": "project-real-video",
        "prompt": "真实生活方式商品广告，镜头自然推进",
        "negative_prompt": "闪烁、变形",
        "duration_seconds": 5,
        "aspect_ratio": "9:16",
        "reference_urls": [
            "https://mock.local/reference.mp4",
            "https://assets.example.com/product.png",
        ],
        "provider_parameters": {
            "seed": 42,
            "resolution": "720P",
            "generate_audio": True,
            "watermark": False,
            "camera_fixed": True,
            "return_last_frame": True,
            "motion_strength": 0.65,
            "callback_url": "https://unsafe.example/callback",
        },
    }
    payload.update(overrides)
    return VideoGenerationRequest.model_validate(payload)


@pytest.mark.asyncio
async def test_submit_builds_seedance_payload_with_safe_parameters() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/api/v3/contents/generations/tasks"
        assert request.headers["Authorization"] == "Bearer ark-secret"
        assert request.extensions["timeout"]["read"] == 12.5
        payload = json.loads(request.content)
        assert payload["model"] == "doubao-seedance-test"
        assert payload["duration"] == 5
        assert payload["ratio"] == "9:16"
        assert payload["seed"] == 42
        assert payload["resolution"] == "720p"
        assert payload["generate_audio"] is True
        assert payload["watermark"] is False
        assert payload["return_last_frame"] is True
        assert "camera_fixed" not in payload
        assert "callback_url" not in payload
        assert payload["content"][1] == {
            "type": "image_url",
            "image_url": {"url": "https://assets.example.com/product.png"},
            "role": "reference_image",
        }
        assert len(payload["content"]) == 2
        prompt = payload["content"][0]["text"]
        assert prompt == (
            "真实生活方式商品广告，镜头自然推进\n\n禁止内容：闪烁、变形"
        )
        assert "motion_strength" not in prompt
        return httpx.Response(200, json={"id": "cgt-submit-001"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = RealVideoProvider(
            api_key="ark-secret",
            model="doubao-seedance-test",
            request_timeout_seconds=12.5,
            poll_interval_seconds=0,
            client=client,
        )
        task = await provider.submit(request=_video_request())

    assert task.task_id == "cgt-submit-001"
    assert task.provider == "seedance"
    assert task.is_mock is False
    assert task.status is VideoTaskStatus.QUEUED
    assert task.progress == 0


@pytest.mark.asyncio
async def test_submit_maps_reference_media_to_documented_content_roles() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        content = json.loads(request.content)["content"]
        assert content[1:] == [
            {
                "type": "image_url",
                "image_url": {"url": "data:image/png;base64,ZmFrZQ=="},
                "role": "reference_image",
            },
            {
                "type": "image_url",
                "image_url": {"url": "https://assets.example.com/product.jpg?version=1"},
                "role": "reference_image",
            },
            {
                "type": "video_url",
                "video_url": {"url": "https://assets.example.com/demo.mp4"},
                "role": "reference_video",
            },
            {
                "type": "audio_url",
                "audio_url": {"url": "https://assets.example.com/voice.m4a"},
                "role": "reference_audio",
            },
        ]
        return httpx.Response(200, json={"id": "gw-media-001"})

    request = _video_request(
        reference_urls=[
            "data:image/png;base64,ZmFrZQ==",
            "https://assets.example.com/product.jpg?version=1",
            "https://assets.example.com/demo.mp4",
            "https://assets.example.com/voice.m4a",
        ]
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = RealVideoProvider(
            api_key="yg-secret",
            model="doubao-seedance-2.0",
            poll_interval_seconds=0,
            client=client,
        )
        task = await provider.submit(request=request)

    assert task.task_id == "gw-media-001"


@pytest.mark.asyncio
async def test_submit_supports_yg_gateway_paths_and_model() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/api/v3/contents/generations/tasks"
        assert dict(request.url.params) == {"beta": "true"}
        assert json.loads(request.content)["model"] == "doubao-seedance-2.0"
        return httpx.Response(200, json={"gateway_task_id": "yg-submit-001"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = RealVideoProvider(
            api_key="yg-secret",
            model="doubao-seedance-2.0",
            base_url="http://video.example.test",
            generation_path="/api/v3/contents/generations/tasks?beta=true",
            status_path_template=(
                "/api/v3/contents/generations/tasks/{task_id}?beta=true"
            ),
            poll_interval_seconds=0,
            client=client,
        )
        task = await provider.submit(request=_video_request())

    assert task.task_id == "yg-submit-001"


@pytest.mark.asyncio
async def test_submit_accepts_gateway_task_id_aliases() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"task_id": "yg-task-id-001"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = RealVideoProvider(
            api_key="yg-secret",
            model="doubao-seedance-2.0",
            poll_interval_seconds=0,
            client=client,
        )
        task = await provider.submit(request=_video_request())

    assert task.task_id == "yg-task-id-001"


@pytest.mark.asyncio
async def test_get_status_supports_yg_template_and_encodes_task_id() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.raw_path.split(b"?", maxsplit=1)[0] == (
            b"/api/v3/contents/generations/tasks/task%2Fwith%20space"
        )
        assert dict(request.url.params) == {"beta": "true"}
        return httpx.Response(
            200,
            json={
                "id": "task/with space",
                "status": "succeeded",
                "content": {"video_url": "https://cdn.example.com/yg-result.mp4"},
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = RealVideoProvider(
            api_key="yg-secret",
            model="doubao-seedance-2.0",
            base_url="http://video.example.test",
            status_path_template=(
                "/api/v3/contents/generations/tasks/{task_id}?beta=true"
            ),
            poll_interval_seconds=0,
            client=client,
        )
        task = await provider.get_status(task_id="task/with space")

    assert task.result_url == "https://cdn.example.com/yg-result.mp4"


@pytest.mark.asyncio
async def test_submit_rejects_duration_over_seedance_limit_before_request() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        pytest.fail("duration validation must happen before the HTTP request")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = RealVideoProvider(
            api_key="ark-secret",
            model="doubao-seedance-test",
            poll_interval_seconds=0,
            client=client,
        )
        with pytest.raises(
            ValueError,
            match="Seedance duration must be between 5 and 15 seconds",
        ):
            await provider.submit(request=_video_request(duration_seconds=20))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("provider_status", "expected_status", "expected_progress"),
    [
        ("queued", VideoTaskStatus.QUEUED, 0),
        ("creating", VideoTaskStatus.QUEUED, 0),
        ("submitted", VideoTaskStatus.QUEUED, 0),
        ("running", VideoTaskStatus.PROCESSING, None),
        ("cancelled", VideoTaskStatus.CANCELLED, 1),
    ],
)
async def test_get_status_maps_non_success_states(
    provider_status: str,
    expected_status: VideoTaskStatus,
    expected_progress: float | None,
) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/api/v3/contents/generations/tasks/cgt-status-001"
        return httpx.Response(
            200,
            json={"id": "cgt-upstream-001", "status": provider_status},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = RealVideoProvider(
            api_key="ark-secret",
            model="doubao-seedance-test",
            poll_interval_seconds=0,
            client=client,
        )
        task = await provider.get_status(task_id="cgt-status-001")

    assert task.status is expected_status
    assert task.progress == expected_progress
    assert task.task_id == "cgt-status-001"


@pytest.mark.asyncio
async def test_get_status_returns_succeeded_video_result() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "id": "cgt-result-001",
                "status": "succeeded",
                "content": {"video_url": "https://cdn.example.com/result.mp4"},
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = RealVideoProvider(
            api_key="ark-secret",
            model="doubao-seedance-test",
            poll_interval_seconds=0,
            client=client,
        )
        task = await provider.get_status(task_id="cgt-result-001")

    assert task.status is VideoTaskStatus.COMPLETED
    assert task.progress == 1
    assert task.result_url == "https://cdn.example.com/result.mp4"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("provider_status", "error", "expected_code"),
    [
        (
            "failed",
            {"code": "OutputVideoSensitiveContentDetected", "message": "unsafe output"},
            "OutputVideoSensitiveContentDetected",
        ),
        ("expired", None, "SEEDANCE_TASK_EXPIRED"),
    ],
)
async def test_get_status_returns_diagnostic_failures(
    provider_status: str,
    error: dict[str, str] | None,
    expected_code: str,
) -> None:
    response_payload: dict[str, object] = {
        "id": "cgt-failed-001",
        "status": provider_status,
    }
    if error is not None:
        response_payload["error"] = error

    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=response_payload)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = RealVideoProvider(
            api_key="ark-secret",
            model="doubao-seedance-test",
            poll_interval_seconds=0,
            client=client,
        )
        task = await provider.get_status(task_id="cgt-failed-001")

    assert task.status is VideoTaskStatus.FAILED
    assert task.error_code == expected_code
    assert task.error_message


@pytest.mark.asyncio
async def test_http_error_exposes_status_and_provider_error_without_secret() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            429,
            json={
                "error": {
                    "code": "QuotaExceeded",
                    "message": "The request has exceeded the quota",
                }
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = RealVideoProvider(
            api_key="ark-secret",
            model="doubao-seedance-test",
            poll_interval_seconds=0,
            client=client,
        )
        with pytest.raises(RealVideoProviderError) as caught:
            await provider.submit(request=_video_request())

    assert caught.value.status_code == 429
    assert caught.value.error_code == "QuotaExceeded"
    assert "QuotaExceeded" in str(caught.value)
    assert "ark-secret" not in str(caught.value)


@pytest.mark.asyncio
async def test_http_error_accepts_fastapi_detail_message() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"detail": "任务不存在"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = RealVideoProvider(
            api_key="yg-secret",
            model="doubao-seedance-2.0",
            poll_interval_seconds=0,
            client=client,
        )
        with pytest.raises(RealVideoProviderError, match="任务不存在"):
            await provider.get_status(task_id="missing")


@pytest.mark.asyncio
async def test_transport_timeout_is_wrapped_with_request_timeout() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("provider stalled", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = RealVideoProvider(
            api_key="ark-secret",
            model="doubao-seedance-test",
            request_timeout_seconds=7,
            poll_interval_seconds=0,
            client=client,
        )
        with pytest.raises(RealVideoProviderError, match="timed out after 7 seconds"):
            await provider.get_status(task_id="cgt-timeout-001")
