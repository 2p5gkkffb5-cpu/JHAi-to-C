from __future__ import annotations

import asyncio
from collections.abc import Mapping
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any

import httpx

from jhai_to_c.contracts.research import EvidenceType, ResearchSource
from jhai_to_c.providers.interfaces import (
    ResearchProviderResult,
    ResearchQuery,
)

DEFAULT_BASE_URL = "https://api.bocha.cn/v1"
MAX_SOURCES = 50


class RealResearchProviderError(RuntimeError):
    """A credential-safe failure returned by the Bocha adapter."""

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


class BochaResearchProvider:
    """Bocha Web Search adapter for the workflow ResearchProvider boundary."""

    provider_name = "bocha"
    is_mock = False

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        request_timeout_seconds: float = 30,
        max_results: int = 8,
        max_retries: int = 2,
        retry_base_delay_seconds: float = 0.5,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        api_key = api_key.strip()
        base_url = base_url.strip().rstrip("/")
        if not api_key:
            raise ValueError("Bocha api_key must not be empty")
        if not base_url:
            raise ValueError("Bocha base_url must not be empty")
        if request_timeout_seconds <= 0:
            raise ValueError("request_timeout_seconds must be greater than zero")
        if not 1 <= max_results <= 50:
            raise ValueError("max_results must be between 1 and 50")
        if max_retries < 0:
            raise ValueError("max_retries must be greater than or equal to zero")
        if retry_base_delay_seconds < 0:
            raise ValueError("retry_base_delay_seconds must be greater than or equal to zero")

        self.api_key = api_key
        self.base_url = base_url
        self.request_timeout_seconds = request_timeout_seconds
        self.max_results = max_results
        self.max_retries = max_retries
        self.retry_base_delay_seconds = retry_base_delay_seconds
        self._client = client

    async def search(self, *, queries: list[ResearchQuery]) -> ResearchProviderResult:
        sources: list[ResearchSource] = []
        seen_urls: set[str] = set()

        for query in queries:
            payload = await self._search_one(query.query)
            for item in _web_results(payload):
                url = _nonempty_string(item.get("url"))
                if url is None or url in seen_urls:
                    continue
                seen_urls.add(url)

                title = _nonempty_string(item.get("name")) or url
                summary = (
                    _nonempty_string(item.get("summary"))
                    or _nonempty_string(item.get("snippet"))
                    or title
                )
                sources.append(
                    ResearchSource(
                        source_id=f"bocha-{sha256(url.encode()).hexdigest()[:24]}",
                        title=title,
                        evidence_type=EvidenceType.EXTERNAL_SOURCE,
                        url=url,
                        summary=summary,
                        retrieved_at=datetime.now(UTC),
                    )
                )
                if len(sources) >= MAX_SOURCES:
                    return ResearchProviderResult(
                        provider=self.provider_name,
                        is_mock=False,
                        sources=sources,
                    )

        return ResearchProviderResult(
            provider=self.provider_name,
            is_mock=False,
            sources=sources,
        )

    async def _search_one(self, query: str) -> dict[str, Any]:
        path = "/web-search"
        url = f"{self.base_url}{path}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        request_payload = {
            "query": query,
            "freshness": "noLimit",
            "summary": True,
            "count": self.max_results,
        }

        attempts = self.max_retries + 1
        for attempt in range(attempts):
            try:
                if self._client is not None:
                    response = await self._client.post(
                        url,
                        headers=headers,
                        json=request_payload,
                        timeout=self.request_timeout_seconds,
                    )
                else:
                    async with httpx.AsyncClient() as client:
                        response = await client.post(
                            url,
                            headers=headers,
                            json=request_payload,
                            timeout=self.request_timeout_seconds,
                        )
            except httpx.TimeoutException as exc:
                if attempt < self.max_retries:
                    await self._backoff(attempt)
                    continue
                raise RealResearchProviderError(
                    "Bocha POST /web-search timed out after "
                    f"{self.request_timeout_seconds:g} seconds"
                ) from exc
            except httpx.RequestError as exc:
                if attempt < self.max_retries:
                    await self._backoff(attempt)
                    continue
                raise RealResearchProviderError(
                    "Bocha POST /web-search transport error: "
                    f"{type(exc).__name__}: {exc}"
                ) from exc

            payload = _response_payload(response)
            provider_code = _provider_code(payload)
            status_code = response.status_code
            is_error = response.is_error or (provider_code is not None and provider_code != 200)
            if not is_error:
                return _unwrap_data(payload)

            effective_status = provider_code or status_code
            if _is_retryable(effective_status) and attempt < self.max_retries:
                await self._backoff(attempt, response.headers.get("Retry-After"))
                continue

            detail = _error_message(payload) or response.reason_phrase or "request failed"
            raise RealResearchProviderError(
                f"Bocha POST /web-search failed (code={effective_status}): {detail}",
                status_code=status_code,
                error_code=str(effective_status),
            )

        raise AssertionError("Bocha retry loop exited without returning or raising")

    async def _backoff(self, attempt: int, retry_after: str | None = None) -> None:
        delay = _retry_after_seconds(retry_after)
        if delay is None:
            delay = self.retry_base_delay_seconds * (2**attempt)
        if delay > 0:
            await asyncio.sleep(delay)


def _response_payload(response: httpx.Response) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError as exc:
        raise RealResearchProviderError(
            f"Bocha response was not valid JSON (HTTP {response.status_code})",
            status_code=response.status_code,
        ) from exc
    if not isinstance(payload, dict):
        raise RealResearchProviderError(
            f"Bocha response must be a JSON object (HTTP {response.status_code})",
            status_code=response.status_code,
        )
    return payload


def _unwrap_data(payload: Mapping[str, Any]) -> dict[str, Any]:
    data = payload.get("data")
    if isinstance(data, dict):
        return data
    return dict(payload)


def _web_results(payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    web_pages = payload.get("webPages")
    if not isinstance(web_pages, Mapping):
        return []
    values = web_pages.get("value")
    if not isinstance(values, list):
        return []
    return [item for item in values if isinstance(item, Mapping)]


def _provider_code(payload: Mapping[str, Any]) -> int | None:
    code = payload.get("code")
    if isinstance(code, bool):
        return None
    if isinstance(code, int):
        return code
    if isinstance(code, str) and code.isdigit():
        return int(code)
    return None


def _error_message(payload: Mapping[str, Any]) -> str | None:
    error = payload.get("error")
    if isinstance(error, Mapping):
        return _nonempty_string(error.get("message")) or _nonempty_string(error.get("msg"))
    return _nonempty_string(payload.get("msg")) or _nonempty_string(payload.get("message"))


def _is_retryable(status_code: int) -> bool:
    return status_code in {408, 409, 429} or 500 <= status_code < 600


def _retry_after_seconds(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        seconds = float(value)
    except ValueError:
        return None
    return max(0, min(seconds, 60))


def _nonempty_string(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None
