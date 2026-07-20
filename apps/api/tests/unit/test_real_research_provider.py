import json

import httpx
import pytest

from jhai_to_c.contracts.research import EvidenceType
from jhai_to_c.providers.interfaces import ResearchQuery
from jhai_to_c.providers.real.research import (
    BochaResearchProvider,
    RealResearchProviderError,
)


def _response(*items: dict[str, object]) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "code": 200,
            "msg": None,
            "data": {
                "_type": "SearchResponse",
                "webPages": {"value": list(items)},
            },
        },
    )


@pytest.mark.asyncio
async def test_search_maps_bocha_web_pages_and_deduplicates_urls() -> None:
    requests: list[dict[str, object]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert str(request.url) == "https://api.bocha.cn/v1/web-search"
        assert request.headers["Authorization"] == "Bearer bocha-secret"
        payload = json.loads(request.content)
        requests.append(payload)
        assert payload == {
            "query": payload["query"],
            "freshness": "noLimit",
            "summary": True,
            "count": 3,
        }
        if len(requests) == 1:
            return _response(
                {
                    "id": "one",
                    "name": "来源一",
                    "url": "https://example.com/one",
                    "summary": "来源一的完整摘要",
                },
                {
                    "id": "shared",
                    "name": "共享来源",
                    "url": "https://example.com/shared",
                    "snippet": "共享来源的片段",
                },
            )
        return _response(
            {
                "id": "shared-again",
                "name": "共享来源重复项",
                "url": "https://example.com/shared",
                "summary": "不应重复写入",
            },
            {
                "id": "two",
                "name": "来源二",
                "url": "https://example.com/two",
                "snippet": "来源二的片段",
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = BochaResearchProvider(
            api_key="bocha-secret",
            max_results=3,
            client=client,
        )
        result = await provider.search(
            queries=[
                ResearchQuery(query="第一个查询"),
                ResearchQuery(query="第二个查询"),
            ]
        )

    assert [request["query"] for request in requests] == ["第一个查询", "第二个查询"]
    assert result.provider == "bocha"
    assert result.is_mock is False
    assert [source.url for source in result.sources] == [
        "https://example.com/one",
        "https://example.com/shared",
        "https://example.com/two",
    ]
    assert result.sources[0].summary == "来源一的完整摘要"
    assert result.sources[1].summary == "共享来源的片段"
    assert all(source.evidence_type is EvidenceType.EXTERNAL_SOURCE for source in result.sources)
    assert all(source.retrieved_at is not None for source in result.sources)


@pytest.mark.asyncio
async def test_search_retries_rate_limit_then_succeeds() -> None:
    attempts = 0

    async def handler(_: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(
                429,
                headers={"Retry-After": "0"},
                json={"code": 429, "msg": "请求过于频繁"},
            )
        return _response(
            {
                "name": "恢复后的结果",
                "url": "https://example.com/recovered",
                "summary": "限流重试成功",
            }
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = BochaResearchProvider(
            api_key="bocha-secret",
            max_retries=1,
            retry_base_delay_seconds=0,
            client=client,
        )
        result = await provider.search(queries=[ResearchQuery(query="测试限流")])

    assert attempts == 2
    assert result.sources[0].title == "恢复后的结果"


@pytest.mark.asyncio
async def test_search_error_does_not_expose_api_key() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"code": 401, "msg": "API KEY 无效"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = BochaResearchProvider(
            api_key="bocha-secret",
            max_retries=0,
            client=client,
        )
        with pytest.raises(RealResearchProviderError) as caught:
            await provider.search(queries=[ResearchQuery(query="测试鉴权")])

    assert caught.value.status_code == 401
    assert caught.value.error_code == "401"
    assert "API KEY 无效" in str(caught.value)
    assert "bocha-secret" not in str(caught.value)
