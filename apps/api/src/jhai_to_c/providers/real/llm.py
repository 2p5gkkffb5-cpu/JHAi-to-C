import asyncio
import json
from time import perf_counter
from typing import Any

import httpx
from pydantic import BaseModel, SecretStr, ValidationError

from jhai_to_c.providers.interfaces import StructuredGenerationResult


class RealLLMProviderError(RuntimeError):
    """Base error for failures produced by the real LLM provider."""


class RealLLMHTTPError(RealLLMProviderError):
    """A non-retryable HTTP response from the upstream provider."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        super().__init__(f"LLM provider returned HTTP {status_code}: {detail}")


class RealLLMRetryExhaustedError(RealLLMProviderError):
    """All attempts for a retryable upstream failure were exhausted."""


class RealLLMTimeoutError(RealLLMProviderError):
    """The complete LLM operation exceeded its timeout budget."""


class RealLLMResponseError(RealLLMProviderError):
    """The upstream response did not match the chat-completions envelope."""


class RealLLMValidationError(RealLLMResponseError):
    """The structured content failed the requested Pydantic schema."""


class RealAgentModelProvider:
    """Grsai OpenAI-compatible structured-output provider."""

    provider_name = "grsai"
    is_mock = False

    def __init__(
        self,
        *,
        api_key: str | SecretStr,
        base_url: str,
        model: str,
        client: httpx.AsyncClient | None = None,
        timeout_seconds: int = 60,
        max_retries: int = 2,
        retry_base_delay_seconds: float = 0.5,
    ) -> None:
        secret = api_key.get_secret_value() if isinstance(api_key, SecretStr) else api_key
        if not secret.strip():
            raise ValueError("api_key must not be empty")
        if not base_url.strip():
            raise ValueError("base_url must not be empty")
        if not model.strip():
            raise ValueError("model must not be empty")
        if max_retries < 0:
            raise ValueError("max_retries must be greater than or equal to zero")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero")
        if retry_base_delay_seconds < 0:
            raise ValueError("retry_base_delay_seconds must be greater than or equal to zero")

        self.api_key = secret
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.client = client
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.retry_base_delay_seconds = retry_base_delay_seconds

    async def generate_structured[OutputT: BaseModel](
        self,
        *,
        system_prompt: str,
        input_data: dict[str, Any],
        output_model: type[OutputT],
        model: str | None = None,
        timeout_seconds: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> StructuredGenerationResult[OutputT]:
        resolved_timeout = self.timeout_seconds if timeout_seconds is None else timeout_seconds
        if resolved_timeout <= 0:
            raise ValueError("timeout_seconds must be greater than zero")

        started = perf_counter()
        resolved_model = model or self.model
        output_schema = json.dumps(
            output_model.model_json_schema(),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        structured_system_prompt = (
            f"{system_prompt}\n\n"
            "你必须只返回一个有效的 JSON 对象，不要返回 Markdown 代码块或额外说明。"
            f"输出必须符合以下 JSON Schema：\n{output_schema}"
        )
        user_text = json.dumps(
            input_data,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        image_urls = [] if metadata is None else metadata.get("image_urls", [])
        if image_urls:
            if not isinstance(image_urls, list) or not all(
                isinstance(url, str) and url for url in image_urls
            ):
                raise ValueError("metadata.image_urls must be a list of non-empty strings")
            user_content: str | list[dict[str, Any]] = [
                {"type": "text", "text": user_text},
                *[
                    {"type": "image_url", "image_url": {"url": url}}
                    for url in image_urls[:12]
                ],
            ]
        else:
            user_content = user_text
        payload = {
            "model": resolved_model,
            "messages": [
                {"role": "system", "content": structured_system_prompt},
                {
                    "role": "user",
                    "content": user_content,
                },
            ],
            "stream": False,
        }

        owned_client = self.client is None
        client = self.client or httpx.AsyncClient()
        try:
            try:
                async with asyncio.timeout(resolved_timeout):
                    response = await self._post_with_retries(client, payload, resolved_timeout)
            except TimeoutError as exc:
                raise RealLLMTimeoutError(
                    f"LLM generation exceeded the {resolved_timeout}s timeout budget"
                ) from exc
        finally:
            if owned_client:
                await client.aclose()

        response_payload = self._response_payload(response)
        raw_output = self._response_content(response_payload)
        try:
            output = output_model.model_validate_json(self._structured_json(raw_output))
        except ValidationError as exc:
            raise RealLLMValidationError(
                f"LLM structured output failed {output_model.__name__} validation: {exc}"
            ) from exc

        usage = response_payload.get("usage")
        usage_data = usage if isinstance(usage, dict) else {}
        return StructuredGenerationResult[OutputT](
            output=output,
            raw_output=raw_output,
            provider=self.provider_name,
            model=resolved_model,
            input_tokens=self._token_count(usage_data.get("prompt_tokens")),
            output_tokens=self._token_count(usage_data.get("completion_tokens")),
            duration_ms=max(0, round((perf_counter() - started) * 1000)),
        )

    async def _post_with_retries(
        self,
        client: httpx.AsyncClient,
        payload: dict[str, Any],
        timeout_seconds: int,
    ) -> httpx.Response:
        attempts = self.max_retries + 1
        for attempt in range(attempts):
            try:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                    timeout=timeout_seconds,
                )
            except httpx.TransportError as exc:
                if attempt >= self.max_retries:
                    raise RealLLMRetryExhaustedError(
                        f"LLM transport failed after {attempts} attempts: {exc}"
                    ) from exc
                await self._backoff(attempt)
                continue

            if 200 <= response.status_code < 300:
                return response

            detail = self._response_detail(response)
            if self._is_retryable_status(response.status_code):
                if attempt >= self.max_retries:
                    raise RealLLMRetryExhaustedError(
                        "LLM provider retryable HTTP failure exhausted "
                        f"after {attempts} attempts: {response.status_code} {detail}"
                    )
                await self._backoff(attempt)
                continue
            raise RealLLMHTTPError(response.status_code, detail)

        raise AssertionError("retry loop exited without returning or raising")

    async def _backoff(self, attempt: int) -> None:
        delay = self.retry_base_delay_seconds * (2**attempt)
        if delay > 0:
            await asyncio.sleep(delay)

    @staticmethod
    def _is_retryable_status(status_code: int) -> bool:
        return status_code in {408, 409, 429} or 500 <= status_code < 600

    @staticmethod
    def _response_payload(response: httpx.Response) -> dict[str, Any]:
        try:
            payload = response.json()
        except ValueError as exc:
            raise RealLLMResponseError("LLM provider returned a non-JSON response") from exc
        if not isinstance(payload, dict):
            raise RealLLMResponseError("LLM provider response must be a JSON object")
        return payload

    @staticmethod
    def _response_content(payload: dict[str, Any]) -> str:
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            raise RealLLMResponseError("LLM provider response is missing choices[0]")
        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            raise RealLLMResponseError("LLM provider choices[0] must be an object")
        message = first_choice.get("message")
        if not isinstance(message, dict):
            raise RealLLMResponseError("LLM provider response is missing choices[0].message")
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            refusal = message.get("refusal")
            suffix = f": {refusal}" if isinstance(refusal, str) and refusal else ""
            raise RealLLMResponseError(
                f"LLM provider response is missing choices[0].message.content{suffix}"
            )
        return content

    @staticmethod
    def _structured_json(content: str) -> str:
        """Remove a Markdown fence only when it wraps the complete JSON response."""
        stripped = content.strip()
        lines = stripped.splitlines()
        if (
            len(lines) >= 3
            and lines[0].strip().casefold() in {"```", "```json"}
            and lines[-1].strip() == "```"
        ):
            return "\n".join(lines[1:-1]).strip()
        return content

    @staticmethod
    def _response_detail(response: httpx.Response) -> str:
        try:
            payload = response.json()
        except ValueError:
            return (response.text.strip() or "no response body")[:500]
        if isinstance(payload, dict):
            error = payload.get("error")
            if isinstance(error, dict) and isinstance(error.get("message"), str):
                return error["message"][:500]
            if isinstance(error, str):
                return error[:500]
        return json.dumps(payload, ensure_ascii=False)[:500]

    @staticmethod
    def _token_count(value: Any) -> int | None:
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            return value
        return None
