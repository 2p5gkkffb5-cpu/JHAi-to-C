from typing import Any

import pytest

from jhai_to_c.agents.intent import INTENT_ROUTER_TIMEOUT_SECONDS
from jhai_to_c.contracts.intent import IntentDecision, TaskIntent
from jhai_to_c.providers.mock import (
    DeterministicMockAgentModelProvider,
    DeterministicMockResearchProvider,
    DeterministicMockVideoProvider,
    MockProviderControl,
)
from jhai_to_c.providers.real.llm import RealLLMTimeoutError
from jhai_to_c.workflow import build_content_project_graph
from jhai_to_c.workflow.errors import CapabilityUnavailableError


class RecordingModelProvider(DeterministicMockAgentModelProvider):
    def __init__(self) -> None:
        super().__init__(MockProviderControl(latency_ms=0))
        self.calls: list[dict[str, Any]] = []

    async def generate_structured(self, **kwargs: Any):
        self.calls.append(kwargs)
        return await super().generate_structured(**kwargs)


class TimeoutOnIntentModelProvider(RecordingModelProvider):
    async def generate_structured(self, **kwargs: Any):
        self.calls.append(kwargs)
        if kwargs["output_model"] is IntentDecision:
            raise RealLLMTimeoutError("test timeout")
        return await DeterministicMockAgentModelProvider.generate_structured(self, **kwargs)


def _state(request_text: str, requested_mode: str = "auto") -> dict[str, Any]:
    return {
        "project_id": "intent-routing-test",
        "request_text": request_text,
        "requested_mode": requested_mode,
        "references": [],
        "target_platform": "douyin",
        "duration_seconds": 10,
        "aspect_ratio": "9:16",
        "completed_nodes": [],
        "provider_usage": {},
        "agent_feedback": {},
        "agent_attempts": {},
        "retry_count": 0,
        "errors": [],
    }


def _graph(provider: RecordingModelProvider):
    control = MockProviderControl(latency_ms=0)
    return build_content_project_graph(
        agent_model_provider=provider,
        research_provider=DeterministicMockResearchProvider(control),
        video_provider=DeterministicMockVideoProvider(control),
        enable_intent_routing=True,
    )


@pytest.mark.asyncio
async def test_auto_router_sends_direct_video_request_to_video_provider_only() -> None:
    provider = RecordingModelProvider()
    final_state = await _graph(provider).ainvoke(_state("让这张图片里的模特缓慢转身"))

    assert final_state["intent_decision"]["intent"] == TaskIntent.VIDEO_GENERATION
    assert final_state["completed_nodes"] == ["intent_router", "video_generation"]
    assert [call["output_model"].__name__ for call in provider.calls] == ["IntentDecision"]
    assert final_state["video_prompt"]["prompt"] == "让这张图片里的模特缓慢转身"
    assert final_state["video_task"]["status"] == "completed"


@pytest.mark.asyncio
async def test_auto_router_keeps_multi_stage_request_on_full_agent_graph() -> None:
    provider = RecordingModelProvider()
    final_state = await _graph(provider).ainvoke(
        _state("请研究受众并策划一套新品短视频文案和分镜")
    )

    assert final_state["intent_decision"]["intent"] == TaskIntent.FULL_CREATION
    assert final_state["completed_nodes"] == [
        "intent_router",
        "director",
        "research",
        "production",
        "video_generation",
    ]
    assert [call["output_model"].__name__ for call in provider.calls] == [
        "IntentDecision",
        "DirectorOutput",
        "ResearchStrategyOutput",
        "ProductionPackageOutput",
    ]


@pytest.mark.asyncio
async def test_explicit_mode_is_a_deterministic_override() -> None:
    provider = RecordingModelProvider()
    final_state = await _graph(provider).ainvoke(
        _state("帮我策划一条完整广告", requested_mode="video_generation")
    )

    assert final_state["intent_decision"] == {
        "intent": "video_generation",
        "confidence": 1.0,
        "reason_code": "explicit_mode",
    }
    assert provider.calls == []
    assert final_state["completed_nodes"] == ["intent_router", "video_generation"]


@pytest.mark.asyncio
async def test_explicit_video_clone_runs_the_independent_clone_pipeline() -> None:
    provider = RecordingModelProvider()
    state = _state(
        "复刻强度：平衡复刻\n改编目标：替换成新品咖啡机",
        requested_mode="video_clone",
    )
    state["references"] = [
        {
            "type": "reference_video",
            "id": "reference-video",
            "label": "@参考.mp4",
            "snapshot": {"url": "https://example.com/reference.mp4"},
        },
        {
            "type": "image",
            "id": "replacement-image",
            "label": "@咖啡机.png",
            "snapshot": {"url": "https://example.com/coffee.png"},
        },
    ]

    final_state = await _graph(provider).ainvoke(state)

    assert final_state["intent_decision"]["intent"] == TaskIntent.VIDEO_CLONE
    assert final_state["completed_nodes"] == [
        "intent_router",
        "video_clone_analysis",
        "video_clone_mapping",
        "video_clone_prompt",
        "video_generation",
        "video_clone_review",
    ]
    assert [call["output_model"].__name__ for call in provider.calls] == [
        "VideoCloneMappingOutput",
        "VideoClonePromptOutput",
    ]
    assert final_state["video_clone_analysis"]["analysis_basis"] == "mock_fixture"
    assert final_state["video_clone_mapping"]["replacement_reference_ids"] == [
        "replacement-image"
    ]
    assert final_state["video_prompt"]["reference_ids"] == [
        "replacement-image",
    ]
    assert final_state["video_prompt"]["provider_parameters"] == {
        "motion_strength": 0.65,
        "resolution": "1080p",
        "generate_audio": False,
        "watermark": False,
        "return_last_frame": True,
        "camera_fixed": False,
    }
    assert final_state["video_clone_review"]["status"] == "pass"


@pytest.mark.asyncio
async def test_packaging_runs_only_when_explicitly_selected() -> None:
    provider = RecordingModelProvider()
    final_state = await _graph(provider).ainvoke(
        _state(
            "店铺名叫山屿，主营手作陶瓷，希望是自然克制的风格",
            requested_mode="brand_packaging",
        )
    )

    assert final_state["intent_decision"]["intent"] == TaskIntent.BRAND_PACKAGING
    assert final_state["completed_nodes"] == [
        "intent_router",
        "director",
        "research",
        "brand_packaging",
    ]
    assert [call["output_model"].__name__ for call in provider.calls] == [
        "DirectorOutput",
        "ResearchStrategyOutput",
        "BrandPackagingOutput",
    ]
    assert final_state["brand_packaging"]["assets"]
    assert "video_task" not in final_state


@pytest.mark.asyncio
async def test_auto_router_timeout_falls_back_to_full_creation() -> None:
    provider = TimeoutOnIntentModelProvider()
    final_state = await _graph(provider).ainvoke(_state("帮我制作一条招聘视频"))

    assert final_state["intent_decision"] == {
        "intent": "full_creation",
        "confidence": 0.0,
        "reason_code": "ambiguous_default",
    }
    assert final_state["completed_nodes"] == [
        "intent_router",
        "director",
        "research",
        "production",
        "video_generation",
    ]
    assert provider.calls[0]["timeout_seconds"] == INTENT_ROUTER_TIMEOUT_SECONDS


@pytest.mark.asyncio
async def test_image_intent_fails_with_explicit_capability_error() -> None:
    provider = RecordingModelProvider()

    with pytest.raises(CapabilityUnavailableError, match="image_generation"):
        await _graph(provider).ainvoke(_state("生成一张夏季促销海报"))
