import json

import httpx
import pytest

from jhai_to_c.contracts.director import DirectorOutput
from jhai_to_c.contracts.production import ProductionPackageOutput
from jhai_to_c.contracts.research import ResearchStrategyOutput
from jhai_to_c.providers.mock import (
    DeterministicMockAgentModelProvider,
    DeterministicMockResearchProvider,
    MockProviderControl,
)
from jhai_to_c.providers.real import RealAgentModelProvider, RealVideoProvider
from jhai_to_c.workflow import build_content_project_graph

OUTPUT_MODELS = {
    model.__name__: model
    for model in (
        DirectorOutput,
        ResearchStrategyOutput,
        ProductionPackageOutput,
    )
}


@pytest.mark.asyncio
async def test_real_provider_adapters_run_through_the_existing_langgraph() -> None:
    fixture_provider = DeterministicMockAgentModelProvider(MockProviderControl(latency_ms=0))

    llm_calls = 0

    async def llm_handler(request: httpx.Request) -> httpx.Response:
        nonlocal llm_calls
        llm_calls += 1
        payload = json.loads(request.content)
        system_prompt = payload["messages"][0]["content"]
        schema_name = next(name for name in OUTPUT_MODELS if f'"title":"{name}"' in system_prompt)
        output_model = OUTPUT_MODELS[schema_name]
        input_data = json.loads(payload["messages"][1]["content"])
        fixture = await fixture_provider.generate_structured(
            system_prompt=payload["messages"][0]["content"],
            input_data=input_data,
            output_model=output_model,
        )
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": fixture.raw_output}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 20},
            },
        )

    video_status_calls = 0

    async def video_handler(request: httpx.Request) -> httpx.Response:
        nonlocal video_status_calls
        if request.method == "POST":
            payload = json.loads(request.content)
            assert payload["duration"] == 10
            assert payload["ratio"] == "9:16"
            return httpx.Response(200, json={"id": "cgt-real-workflow"})

        video_status_calls += 1
        if video_status_calls == 1:
            return httpx.Response(
                200,
                json={"id": "cgt-real-workflow", "status": "running"},
            )
        return httpx.Response(
            200,
            json={
                "id": "cgt-real-workflow",
                "status": "succeeded",
                "content": {"video_url": "https://cdn.example.com/real-result.mp4"},
            },
        )

    async with (
        httpx.AsyncClient(transport=httpx.MockTransport(llm_handler)) as llm_client,
        httpx.AsyncClient(transport=httpx.MockTransport(video_handler)) as video_client,
    ):
        graph = build_content_project_graph(
            agent_model_provider=RealAgentModelProvider(
                api_key="llm-key",
                base_url="https://grsaiapi.example/v1",
                model="gemini-3.1-pro",
                client=llm_client,
                retry_base_delay_seconds=0,
            ),
            research_provider=DeterministicMockResearchProvider(MockProviderControl(latency_ms=0)),
            video_provider=RealVideoProvider(
                api_key="video-key",
                base_url="https://ark.example/api/v3",
                model="seedance-endpoint",
                client=video_client,
                poll_interval_seconds=0,
            ),
            video_max_status_polls=5,
        )
        result = await graph.ainvoke(
            {
                "project_id": "project-real-workflow",
                "request_text": "为随行鲜榨杯制作一条10秒商品广告",
                "references": [],
                "target_platform": "douyin",
                "duration_seconds": 10,
                "aspect_ratio": "9:16",
                "completed_nodes": [],
                "provider_usage": {},
                "retry_count": 0,
                "errors": [],
            }
        )

    assert result["video_task"] == {
        "task_id": "cgt-real-workflow",
        "provider": "seedance",
        "is_mock": False,
        "status": "completed",
        "progress": 1.0,
        "result_url": "https://cdn.example.com/real-result.mp4",
        "error_code": None,
        "error_message": None,
    }
    assert result["provider_usage"]["director"]["provider"] == "grsai"
    assert result["provider_usage"]["video_generation"]["provider"] == "seedance"
    assert llm_calls == 3
