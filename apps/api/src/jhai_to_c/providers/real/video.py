from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any
from urllib.parse import quote, urlsplit

import httpx

from jhai_to_c.contracts.video import (
    VideoGenerationRequest,
    VideoTask,
    VideoTaskStatus,
)

DEFAULT_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
DEFAULT_GENERATION_PATH = "/contents/generations/tasks"
DEFAULT_STATUS_PATH_TEMPLATE = "/contents/generations/tasks/{task_id}"

_RATIOS = frozenset({"16:9", "4:3", "1:1", "3:4", "9:16", "21:9", "adaptive"})
_RESOLUTIONS = frozenset({"480p", "720p", "1080p"})
_INLINE_IMAGE_PREFIXES = (
    "data:image/png;base64,",
    "data:image/jpeg;base64,",
    "data:image/webp;base64,",
)
_STATUS_MAP = {
    "creating": VideoTaskStatus.QUEUED,
    "submitted": VideoTaskStatus.QUEUED,
    "queued": VideoTaskStatus.QUEUED,
    "running": VideoTaskStatus.PROCESSING,
    "succeeded": VideoTaskStatus.COMPLETED,
    "failed": VideoTaskStatus.FAILED,
    "expired": VideoTaskStatus.FAILED,
    "cancelled": VideoTaskStatus.CANCELLED,
}


class RealVideoProviderError(RuntimeError):
    """A diagnostic, credential-safe failure returned by the Seedance adapter."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        error_code: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code


class RealVideoProvider:
    """Fire-and-poll adapter for Volcengine Ark Seedance video tasks."""

    provider_name = "seedance"
    is_mock = False

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str = DEFAULT_BASE_URL,
        generation_path: str = DEFAULT_GENERATION_PATH,
        status_path_template: str = DEFAULT_STATUS_PATH_TEMPLATE,
        request_timeout_seconds: float = 30,
        poll_interval_seconds: float = 15,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        api_key = api_key.strip()
        model = model.strip()
        base_url = base_url.strip().rstrip("/")
        generation_path = _validated_path(generation_path, "generation_path")
        status_path_template = _validated_status_path_template(status_path_template)
        if not api_key:
            raise ValueError("Seedance api_key must not be empty")
        if not model:
            raise ValueError("Seedance model must not be empty")
        if not base_url:
            raise ValueError("Seedance base_url must not be empty")
        if request_timeout_seconds <= 0:
            raise ValueError("request_timeout_seconds must be greater than zero")
        if poll_interval_seconds < 0:
            raise ValueError("poll_interval_seconds must not be negative")

        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.generation_path = generation_path
        self.status_path_template = status_path_template
        self.request_timeout_seconds = request_timeout_seconds
        self.poll_interval_seconds = poll_interval_seconds
        self._client = client

    async def submit(self, *, request: VideoGenerationRequest) -> VideoTask:
        payload = self._submit_payload(request)
        response = await self._request("POST", self.generation_path, json=payload)
        task_id = _task_id(response)
        if task_id is None:
            raise RealVideoProviderError(
                "Seedance create-task response is missing a valid task id"
            )
        return VideoTask(
            task_id=task_id,
            provider=self.provider_name,
            is_mock=False,
            status=VideoTaskStatus.QUEUED,
            progress=0,
        )

    async def get_status(self, *, task_id: str) -> VideoTask:
        task_id = task_id.strip()
        if not task_id:
            raise ValueError("task_id must not be empty")
        if self.poll_interval_seconds:
            await asyncio.sleep(self.poll_interval_seconds)

        response = await self._request(
            "GET",
            self.status_path_template.format(task_id=quote(task_id, safe="")),
        )
        provider_status = (_nonempty_string(response.get("status")) or "").lower()
        status = _STATUS_MAP.get(provider_status)
        if status is None:
            raise RealVideoProviderError(
                f"Seedance task {task_id} returned unsupported status {provider_status!r}"
            )

        error_code, error_message = _error_details(response)
        result_url: str | None = None
        if status is VideoTaskStatus.COMPLETED:
            content = response.get("content")
            if isinstance(content, Mapping):
                result_url = _nonempty_string(content.get("video_url"))
            if result_url is None:
                raise RealVideoProviderError(
                    f"Seedance task {task_id} succeeded without content.video_url"
                )
        elif provider_status == "expired":
            error_code = error_code or "SEEDANCE_TASK_EXPIRED"
            error_message = error_message or "Seedance video task expired before completion"
        elif status is VideoTaskStatus.FAILED:
            error_code = error_code or "SEEDANCE_TASK_FAILED"
            error_message = error_message or "Seedance video generation failed"
        elif status is VideoTaskStatus.CANCELLED:
            error_code = error_code or "SEEDANCE_TASK_CANCELLED"
            error_message = error_message or "Seedance video task was cancelled"

        return VideoTask(
            # Gateway responses may replace gw-* with an upstream cgt-* id.
            # Preserve the create-task id so every subsequent poll stays valid.
            task_id=task_id,
            provider=self.provider_name,
            is_mock=False,
            status=status,
            progress=_progress_for(status),
            result_url=result_url,
            error_code=_truncate(error_code, 100),
            error_message=_truncate(error_message, 2000),
        )

    def _submit_payload(self, request: VideoGenerationRequest) -> dict[str, Any]:
        parameters = request.provider_parameters
        duration = parameters.get(
            "duration",
            parameters.get("duration_seconds", request.duration_seconds),
        )
        if isinstance(duration, bool) or not isinstance(duration, int):
            raise ValueError("Seedance duration must be an integer number of seconds")
        if not 5 <= duration <= 15:
            raise ValueError("Seedance duration must be between 5 and 15 seconds")

        ratio = parameters.get("ratio", parameters.get("aspect_ratio", request.aspect_ratio))
        if not isinstance(ratio, str) or ratio not in _RATIOS:
            raise ValueError(f"Unsupported Seedance ratio: {ratio!r}")

        prompt = request.prompt.strip()
        negative_prompt = request.negative_prompt.strip()
        if negative_prompt:
            prompt = f"{prompt}\n\n禁止内容：{negative_prompt}"
        content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
        reference_content = [
            _reference_content(reference_url)
            for reference_url in request.reference_urls
            if _is_remote_reference(reference_url)
        ]
        content.extend(reference_content)

        payload: dict[str, Any] = {
            "content": content,
            "duration": duration,
            "ratio": ratio,
        }
        payload["model"] = self.model

        if "seed" in parameters:
            seed = _safe_int(parameters["seed"], minimum=-1, maximum=2_147_483_647)
            if seed is None:
                raise ValueError("Seedance seed must be an integer between -1 and 2147483647")
            payload["seed"] = seed

        if "resolution" in parameters:
            resolution = parameters["resolution"]
            if not isinstance(resolution, str) or resolution.lower() not in _RESOLUTIONS:
                raise ValueError(f"Unsupported Seedance resolution: {resolution!r}")
            payload["resolution"] = resolution.lower()

        for parameter in (
            "generate_audio",
            "watermark",
            "camera_fixed",
            "return_last_frame",
        ):
            if parameter not in parameters:
                continue
            if parameter == "camera_fixed" and reference_content:
                # Seedance 2.0 rejects camera_fixed in reference-to-video mode.
                # The desired camera behavior remains expressed in the prompt.
                continue
            value = parameters[parameter]
            if not isinstance(value, bool):
                raise ValueError(f"Seedance {parameter} must be a boolean")
            payload[parameter] = value
        return payload

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        try:
            if self._client is not None:
                response = await self._client.request(
                    method,
                    url,
                    headers=headers,
                    json=json,
                    timeout=self.request_timeout_seconds,
                )
            else:
                async with httpx.AsyncClient() as client:
                    response = await client.request(
                        method,
                        url,
                        headers=headers,
                        json=json,
                        timeout=self.request_timeout_seconds,
                    )
        except httpx.TimeoutException as exc:
            raise RealVideoProviderError(
                f"Seedance {method} {path} timed out after {self.request_timeout_seconds:g} seconds"
            ) from exc
        except httpx.RequestError as exc:
            raise RealVideoProviderError(
                f"Seedance {method} {path} transport error: {type(exc).__name__}: {exc}"
            ) from exc

        payload = _response_payload(response)
        if response.is_error:
            error_code, error_message = _error_details(payload)
            detail = error_message or response.reason_phrase or "request failed"
            code_suffix = f", code={error_code}" if error_code else ""
            raise RealVideoProviderError(
                f"Seedance {method} {path} failed "
                f"(HTTP {response.status_code}{code_suffix}): {detail}",
                status_code=response.status_code,
                error_code=error_code,
            )
        return payload


def _response_payload(response: httpx.Response) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError as exc:
        raise RealVideoProviderError(
            f"Seedance response was not valid JSON (HTTP {response.status_code})",
            status_code=response.status_code,
        ) from exc
    if not isinstance(payload, dict):
        raise RealVideoProviderError(
            f"Seedance response must be a JSON object (HTTP {response.status_code})",
            status_code=response.status_code,
        )
    return payload


def _validated_path(value: str, name: str) -> str:
    value = value.strip()
    if not value.startswith("/") or value.startswith("//"):
        raise ValueError(f"Seedance {name} must be a root-relative path")
    return value


def _validated_status_path_template(value: str) -> str:
    value = _validated_path(value, "status_path_template")
    if value.count("{task_id}") != 1:
        raise ValueError(
            "Seedance status_path_template must contain exactly one {task_id} placeholder"
        )
    return value


def _error_details(payload: Mapping[str, Any]) -> tuple[str | None, str | None]:
    error = payload.get("error")
    if isinstance(error, Mapping):
        return _nonempty_string(error.get("code")), _nonempty_string(error.get("message"))
    return _nonempty_string(payload.get("code")), (
        _nonempty_string(payload.get("message"))
        or _nonempty_string(payload.get("detail"))
    )


def _task_id(payload: Mapping[str, Any]) -> str | None:
    for field in ("id", "gateway_task_id", "task_id"):
        value = _nonempty_string(payload.get(field))
        if value is not None:
            return value
    return None


def _nonempty_string(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


def _safe_int(value: object, *, minimum: int, maximum: int) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value if minimum <= value <= maximum else None


def _is_remote_reference(value: object) -> bool:
    if not isinstance(value, str):
        return False
    value = value.strip()
    if value.startswith(_INLINE_IMAGE_PREFIXES):
        return True
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False
    hostname = parsed.hostname.lower()
    return hostname != "mock.local" and not hostname.endswith(".mock.local")


def _reference_content(reference_url: str) -> dict[str, Any]:
    path = urlsplit(reference_url).path.lower()
    if path.endswith((".mp4", ".mov", ".m4v", ".webm")):
        return {
            "type": "video_url",
            "video_url": {"url": reference_url},
            "role": "reference_video",
        }
    if path.endswith((".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg")):
        return {
            "type": "audio_url",
            "audio_url": {"url": reference_url},
            "role": "reference_audio",
        }
    return {
        "type": "image_url",
        "image_url": {"url": reference_url},
        "role": "reference_image",
    }


def _progress_for(status: VideoTaskStatus) -> float | None:
    if status is VideoTaskStatus.QUEUED:
        return 0
    if status in {
        VideoTaskStatus.COMPLETED,
        VideoTaskStatus.FAILED,
        VideoTaskStatus.CANCELLED,
    }:
        return 1
    return None


def _truncate(value: str | None, maximum: int) -> str | None:
    return None if value is None else value[:maximum]
