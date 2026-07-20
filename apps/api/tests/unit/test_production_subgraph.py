from typing import Any

import pytest

from jhai_to_c.agents.production import ProductionAgent, ProductionInput
from jhai_to_c.contracts.director import CreativeBrief
from jhai_to_c.contracts.production import ProductionPackageOutput
from jhai_to_c.contracts.strategy import StrategyOption
from jhai_to_c.providers.mock import (
    DeterministicMockAgentModelProvider,
    MockProviderControl,
)
from jhai_to_c.workflow.errors import InvalidReferenceSubsetError
from jhai_to_c.workflow.production import (
    VIDEO_PROMPT_LINE_LABELS,
    validate_production_package,
)


class RecordingProvider(DeterministicMockAgentModelProvider):
    def __init__(self, scenario: str = "success") -> None:
        super().__init__(MockProviderControl(latency_ms=0, scenario=scenario))
        self.calls: list[dict[str, Any]] = []

    async def generate_structured(self, **kwargs: Any):
        self.calls.append(dict(kwargs))
        return await super().generate_structured(**kwargs)


def _input() -> ProductionInput:
    return ProductionInput(
        creative_brief=CreativeBrief(
            industry="消费品",
            product="便携咖啡机",
            platform="douyin",
            goal="建立认知并引导转化",
            target_audience="年轻消费者",
            content_direction="展示通勤场景中的快速制作",
            duration_seconds=20,
            aspect_ratio="9:16",
            tone=["可信"],
            must_include=[],
            must_avoid=[],
        ),
        selected_strategy=StrategyOption(
            strategy_id="strategy-1",
            name="场景策略",
            summary="场景化演示",
            target_audience="年轻消费者",
            core_message="随时快速制作咖啡",
            selling_points=["便携"],
            hook="通勤也能喝到现做咖啡",
            narrative_structure=["hook", "proof", "cta"],
            visual_direction="明亮竖屏",
            cta="立即了解",
            risks=[],
            scores={
                "brand_fit": 90,
                "conversion_fit": 90,
                "execution_feasibility": 90,
                "differentiation": 90,
            },
        ),
        references=[
            {
                "type": "product",
                "id": "ref-a",
                "label": "@咖啡机",
                "snapshot": {"url": "https://example.com/a"},
            },
            {
                "type": "reference_video",
                "id": "ref-b",
                "label": "@参考视频",
                "snapshot": {"url": "https://example.com/b"},
            },
        ],
    )


@pytest.mark.asyncio
async def test_production_agent_generates_complete_package_in_one_model_call() -> None:
    provider = RecordingProvider()
    agent_input = _input()
    output = await ProductionAgent(provider).execute(agent_input)

    assert ProductionPackageOutput.model_validate(output.model_dump(mode="json")) == output
    validate_production_package(output, agent_input)
    assert len(provider.calls) == 1
    assert provider.calls[0]["metadata"] == {"agent": "production", "node": "production"}
    assert provider.calls[0]["output_model"] is ProductionPackageOutput
    assert output.production_plan.allowed_reference_ids == ["ref-a", "ref-b"]
    assert output.copywriting.voiceover
    assert output.storyboard.shots
    assert output.video_prompt.prompt
    assert [
        line.split("]", 1)[0].removeprefix("[")
        for line in output.video_prompt.prompt.splitlines()
    ] == list(VIDEO_PROMPT_LINE_LABELS)


@pytest.mark.asyncio
async def test_production_package_rejects_unformatted_video_prompt() -> None:
    provider = RecordingProvider()
    agent_input = _input()
    output = await ProductionAgent(provider).execute(agent_input)
    invalid_output = output.model_copy(
        update={
            "video_prompt": output.video_prompt.model_copy(
                update={"prompt": "便携咖啡机商业短视频"}
            )
        }
    )

    with pytest.raises(ValueError, match="exactly 14"):
        validate_production_package(invalid_output, agent_input)

    plus_separated = output.model_copy(
        update={
            "video_prompt": output.video_prompt.model_copy(
                update={"prompt": output.video_prompt.prompt.replace("\n", "+\n", 1)}
            )
        }
    )
    with pytest.raises(ValueError, match="line breaks instead of plus"):
        validate_production_package(plus_separated, agent_input)


@pytest.mark.asyncio
async def test_invalid_package_reference_is_rejected() -> None:
    provider = RecordingProvider("coordinator_invalid_reference")
    agent_input = _input()
    output = await ProductionAgent(provider).execute(agent_input)

    with pytest.raises(InvalidReferenceSubsetError) as raised:
        validate_production_package(output, agent_input)
    assert raised.value.details["invalid_ids"] == ["unknown-reference-id"]
    assert len(provider.calls) == 1
