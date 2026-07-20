from typing import Any

import pytest

from jhai_to_c.agents import (
    DEFAULT_AGENT_CONFIGS,
    AgentName,
    AgentRegistry,
    UnknownAgentError,
)
from jhai_to_c.prompts import PromptLoader
from jhai_to_c.providers.mock import (
    DeterministicMockAgentModelProvider,
    DeterministicMockResearchProvider,
    DeterministicMockVideoProvider,
    MockProviderControl,
)
from jhai_to_c.workflow import build_content_project_graph

PROMPTS = {
    "supervisor": "phase-b prompt: supervisor",
    "research_strategy": "phase-b prompt: research strategy",
    "production": "phase-b prompt: production",
}

EXPECTED_NODE_ORDER = [
    "director",
    "research",
    "production",
    "video_generation",
]


class TrackingRegistry(AgentRegistry):
    def __init__(self) -> None:
        super().__init__(DEFAULT_AGENT_CONFIGS)
        self.lookups: list[AgentName] = []

    def get(self, name: AgentName | str):
        config = super().get(name)
        self.lookups.append(config.name)
        return config


class RecordingProvider(DeterministicMockAgentModelProvider):
    provider_name = "phase-b-recording-provider"

    def __init__(self) -> None:
        super().__init__(MockProviderControl(latency_ms=0))
        self.calls: list[dict[str, Any]] = []

    async def generate_structured(self, **kwargs: Any):
        self.calls.append(dict(kwargs))
        return await super().generate_structured(**kwargs)


def _initial_state() -> dict[str, Any]:
    return {
        "project_id": "phase-b-runtime-wiring",
        "request_text": "为一款便携咖啡机制作 20 秒短视频",
        "references": [],
        "target_platform": "douyin",
        "duration_seconds": 20,
        "aspect_ratio": "9:16",
        "completed_nodes": [],
        "provider_usage": {},
        "retry_count": 0,
        "errors": [],
    }


@pytest.mark.asyncio
async def test_phase_b_graph_uses_registry_prompts_and_one_model_provider(tmp_path) -> None:
    for prompt_name, prompt in PROMPTS.items():
        (tmp_path / f"{prompt_name}.md").write_text(prompt, encoding="utf-8")

    registry = TrackingRegistry()
    prompt_loader = PromptLoader(tmp_path)
    model_provider = RecordingProvider()
    control = MockProviderControl(latency_ms=0)
    graph = build_content_project_graph(
        agent_registry=registry,
        prompt_loader=prompt_loader,
        agent_model_provider=model_provider,
        research_provider=DeterministicMockResearchProvider(control),
        video_provider=DeterministicMockVideoProvider(control),
    )

    node_updates: list[str] = []
    final_state = _initial_state()
    async for update in graph.astream(_initial_state(), stream_mode="updates"):
        node_name, state_update = next(iter(update.items()))
        node_updates.append(node_name)
        final_state.update(state_update)

    assert registry.lookups == [
        AgentName.SUPERVISOR,
        AgentName.RESEARCH,
        AgentName.PRODUCTION,
    ]
    assert [call["system_prompt"] for call in model_provider.calls] == list(PROMPTS.values())
    assert [call["output_model"].__name__ for call in model_provider.calls] == [
        "DirectorOutput",
        "ResearchStrategyOutput",
        "ProductionPackageOutput",
    ]
    assert len(model_provider.calls) == 3
    assert all("model" not in call for call in model_provider.calls)

    assert node_updates == EXPECTED_NODE_ORDER
    assert final_state["completed_nodes"] == [
        "director",
        "research",
        "production",
        "video_generation",
    ]
    assert final_state["video_task"]["status"] == "completed"
    assert set(final_state) >= {
        "director",
        "creative_brief",
        "research",
        "strategies",
        "selected_strategy_id",
        "copywriting",
        "storyboard",
        "video_prompt",
        "video_task",
        "video_task_history",
    }
    assert {
        node_name: final_state["provider_usage"][node_name]["provider"]
        for node_name in final_state["completed_nodes"][:-1]
    } == dict.fromkeys(final_state["completed_nodes"][:-1], model_provider.provider_name)


def test_explicit_empty_registry_is_not_replaced_by_defaults() -> None:
    with pytest.raises(UnknownAgentError):
        build_content_project_graph(agent_registry=AgentRegistry())
