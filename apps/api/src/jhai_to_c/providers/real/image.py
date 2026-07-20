from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import httpx
from pydantic import SecretStr

from jhai_to_c.contracts.image import ImageGenerationRequest, ImageGenerationResult


class RealImageProviderError(RuntimeError):
    """Credential-safe failure returned by the GRS image adapter."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class RealImageProvider:
    provider_name = "grsai"
    is_mock = False

    def __init__(
        self,
        *,
        api_key: str | SecretStr,
        base_url: str,
        model: str,
        request_timeout_seconds: float = 180,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        secret = api_key.get_secret_value() if isinstance(api_key, SecretStr) else api_key
        secret = secret.strip()
        base_url = base_url.strip().rstrip("/")
        model = model.strip()
        if not secret:
            raise ValueError("Image api_key must not be empty")
        if not base_url:
            raise ValueError("Image base_url must not be empty")
        if not model:
            raise ValueError("Image model must not be empty")
        if request_timeout_seconds <= 0:
            raise ValueError("request_timeout_seconds must be greater than zero")

        self.api_key = secret
        self.base_url = base_url
        self.model = model
        self.request_timeout_seconds = request_timeout_seconds
        self._client = client

    async def generate(self, *, request: ImageGenerationRequest) -> ImageGenerationResult:
        response_payload = await self._request(
            {
                "model": self.model,
                "prompt": request.prompt,
                "images": request.images,
                "aspectRatio": request.size.value,
                "replyType": "json",
            }
        )
        status = _nonempty_string(response_payload.get("status"))
        if status != "succeeded":
            detail = _response_detail(response_payload, "request did not succeed")
            raise RealImageProviderError(
                f"Image generation task {status or 'returned no status'}: {detail}"
            )
        image = _first_image(response_payload)
        image_url = _nonempty_string(image.get("url"))
        if image_url is None:
            raise RealImageProviderError(
                "Image generation response is missing results[0].url"
            )

        return ImageGenerationResult(
            image_url=image_url,
            revised_prompt=_nonempty_string(image.get("revised_prompt")),
            provider=self.provider_name,
            model=self.model,
            size=request.size,
            quality=request.quality,
        )

    async def _request(self, payload: dict[str, Any]) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        try:
            if self._client is not None:
                response = await self._client.post(
                    f"{self.base_url}/api/generate",
                    headers=headers,
                    json=payload,
                    timeout=self.request_timeout_seconds,
                )
            else:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        f"{self.base_url}/api/generate",
                        headers=headers,
                        json=payload,
                        timeout=self.request_timeout_seconds,
                    )
        except httpx.TimeoutException as exc:
            raise RealImageProviderError(
                f"Image generation timed out after {self.request_timeout_seconds:g} seconds"
            ) from exc
        except httpx.RequestError as exc:
            raise RealImageProviderError(
                f"Image generation transport error: {type(exc).__name__}"
            ) from exc

        response_payload = _response_payload(response)
        if response.is_error:
            raise RealImageProviderError(
                f"Image generation failed (HTTP {response.status_code}): "
                f"{_response_detail(response_payload, response.reason_phrase)}",
                status_code=response.status_code,
            )
        return response_payload


def _response_payload(response: httpx.Response) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError as exc:
        raise RealImageProviderError(
            f"Image generation response was not valid JSON (HTTP {response.status_code})",
            status_code=response.status_code,
        ) from exc
    if not isinstance(payload, dict):
        raise RealImageProviderError(
            f"Image generation response must be an object (HTTP {response.status_code})",
            status_code=response.status_code,
        )
    return payload


def _first_image(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    results = payload.get("results")
    if not isinstance(results, list) or not results or not isinstance(results[0], Mapping):
        raise RealImageProviderError("Image generation response is missing results[0]")
    return results[0]


def _response_detail(payload: Mapping[str, Any], fallback: str) -> str:
    error = payload.get("error")
    if isinstance(error, str) and error.strip():
        return error.strip()[:500]
    if isinstance(error, Mapping):
        message = _nonempty_string(error.get("message"))
        if message is not None:
            return message[:500]
    return (_nonempty_string(payload.get("detail")) or fallback or "request failed")[:500]


def _nonempty_string(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None
