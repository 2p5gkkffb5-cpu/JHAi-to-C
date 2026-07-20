import json

import httpx
import pytest
from pydantic import Field, ValidationError

from jhai_to_c.contracts.common import ContractModel
from jhai_to_c.providers.real.llm import (
    RealAgentModelProvider,
    RealLLMRetryExhaustedError,
    RealLLMValidationError,
)


class DemoOutput(ContractModel):
    title: str = Field(min_length=1)
    score: int = Field(ge=0, le=100)


def _completion_response(
    content: str,
    *,
    prompt_tokens: int = 12,
    completion_tokens: int = 8,
) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "choices": [{"message": {"role": "assistant", "content": content}}],
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
            },
        },
    )


def _provider(
    client: httpx.AsyncClient,
    *,
    max_retries: int = 2,
) -> RealAgentModelProvider:
    return RealAgentModelProvider(
        api_key="test-api-key",
        base_url="https://grsaiapi.example/v1/",
        model="gemini-3.1-pro",
        client=client,
        max_retries=max_retries,
        retry_base_delay_seconds=0,
    )


@pytest.mark.asyncio
async def test_generate_structured_success() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers.get("Authorization")
        captured["payload"] = json.loads(request.content)
        return _completion_response('{"title":"真实内容","score":96}')

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await _provider(client).generate_structured(
            system_prompt="只返回符合 Schema 的内容",
            input_data={"topic": "杭州餐饮", "duration_seconds": 20},
            output_model=DemoOutput,
            metadata={"agent": "test"},
        )

    assert captured["url"] == "https://grsaiapi.example/v1/chat/completions"
    assert captured["authorization"] == "Bearer test-api-key"
    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert payload["model"] == "gemini-3.1-pro"
    assert payload["stream"] is False
    assert set(payload) == {"model", "messages", "stream"}
    assert payload["messages"][0]["role"] == "system"
    assert payload["messages"][0]["content"].startswith("只返回符合 Schema 的内容")
    assert "只返回一个有效的 JSON 对象" in payload["messages"][0]["content"]
    assert (
        json.dumps(
            DemoOutput.model_json_schema(),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        in payload["messages"][0]["content"]
    )
    assert json.loads(payload["messages"][1]["content"]) == {
        "duration_seconds": 20,
        "topic": "杭州餐饮",
    }
    assert result.output == DemoOutput(title="真实内容", score=96)
    assert result.raw_output == '{"title":"真实内容","score":96}'
    assert result.provider == "grsai"
    assert result.model == "gemini-3.1-pro"
    assert result.input_tokens == 12
    assert result.output_tokens == 8
    assert result.duration_ms >= 0


@pytest.mark.asyncio
async def test_generate_structured_accepts_json_markdown_fence() -> None:
    raw_output = '```json\n{"title":"围栏内容","score":92}\n```'

    def handler(request: httpx.Request) -> httpx.Response:
        del request
        return _completion_response(raw_output)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await _provider(client).generate_structured(
            system_prompt="system",
            input_data={"topic": "markdown-fence"},
            output_model=DemoOutput,
        )

    assert result.output == DemoOutput(title="围栏内容", score=92)
    assert result.raw_output == raw_output


@pytest.mark.asyncio
async def test_generate_structured_attaches_images_as_multimodal_content() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["payload"] = json.loads(request.content)
        return _completion_response('{"title":"关键帧分析","score":91}')

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        await _provider(client).generate_structured(
            system_prompt="分析关键帧",
            input_data={"timestamps": [0.5, 2.5]},
            output_model=DemoOutput,
            metadata={"image_urls": ["data:image/jpeg;base64,AAAA"]},
        )

    payload = captured["payload"]
    assert isinstance(payload, dict)
    content = payload["messages"][1]["content"]
    assert content[0]["type"] == "text"
    assert json.loads(content[0]["text"]) == {"timestamps": [0.5, 2.5]}
    assert content[1] == {
        "type": "image_url",
        "image_url": {"url": "data:image/jpeg;base64,AAAA"},
    }


@pytest.mark.asyncio
async def test_retries_transport_timeout_then_succeeds() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise httpx.ReadTimeout("upstream read timed out", request=request)
        return _completion_response('{"title":"重试成功","score":88}')

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await _provider(client, max_retries=1).generate_structured(
            system_prompt="system",
            input_data={"topic": "timeout"},
            output_model=DemoOutput,
            timeout_seconds=2,
        )

    assert attempts == 2
    assert result.output.title == "重试成功"


@pytest.mark.asyncio
async def test_retries_429_then_succeeds() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(
                429,
                json={"error": {"message": "rate limited"}},
            )
        return _completion_response('{"title":"限流恢复","score":90}')

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await _provider(client, max_retries=1).generate_structured(
            system_prompt="system",
            input_data={"topic": "rate-limit"},
            output_model=DemoOutput,
        )

    assert attempts == 2
    assert result.output.title == "限流恢复"


@pytest.mark.asyncio
async def test_invalid_structured_output_raises_validation_error_without_retry() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        del request
        nonlocal attempts
        attempts += 1
        return _completion_response('{"title":"字段错误","score":"not-a-number"}')

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(RealLLMValidationError) as error:
            await _provider(client, max_retries=2).generate_structured(
                system_prompt="system",
                input_data={"topic": "validation"},
                output_model=DemoOutput,
            )

    assert attempts == 1
    assert isinstance(error.value.__cause__, ValidationError)
    assert "DemoOutput" in str(error.value)


@pytest.mark.asyncio
async def test_retryable_http_failure_raises_after_exhaustion() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        del request
        nonlocal attempts
        attempts += 1
        return httpx.Response(
            503,
            json={"error": {"message": "temporarily unavailable"}},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(RealLLMRetryExhaustedError, match="after 3 attempts"):
            await _provider(client, max_retries=2).generate_structured(
                system_prompt="system",
                input_data={"topic": "exhaustion"},
                output_model=DemoOutput,
            )

    assert attempts == 3
