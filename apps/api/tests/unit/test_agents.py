import pytest

from jhai_to_c.agents.director import DirectorAgent, DirectorInput
from jhai_to_c.agents.production import ProductionAgent, ProductionInput
from jhai_to_c.agents.research import ResearchInput, ResearchStrategyAgent
from jhai_to_c.agents.reviewer import ReviewerAgent, ReviewerInput
from jhai_to_c.contracts.director import DirectorOutput
from jhai_to_c.contracts.review import ReviewStatus
from jhai_to_c.providers.mock import (
    DeterministicMockAgentModelProvider,
    DeterministicMockResearchProvider,
    MockProviderControl,
)


def _model_provider(scenario: str = "success") -> DeterministicMockAgentModelProvider:
    return DeterministicMockAgentModelProvider(MockProviderControl(latency_ms=0, scenario=scenario))


async def _production_inputs():
    request_text = "为一款无糖气泡水制作 20 秒竖屏营销视频"
    provider = _model_provider()
    director = await DirectorAgent(provider).execute(DirectorInput(request_text=request_text))
    research_strategy = await ResearchStrategyAgent(
        provider,
        DeterministicMockResearchProvider(MockProviderControl(latency_ms=0)),
    ).execute(
        ResearchInput(
            request_text=request_text,
            creative_brief=director.creative_brief,
        )
    )
    strategy = research_strategy.strategies
    selected = next(
        option
        for option in strategy.strategy_options
        if option.strategy_id == strategy.recommended_strategy_id
    )
    production = await ProductionAgent(provider).execute(
        ProductionInput(
            creative_brief=director.creative_brief,
            selected_strategy=selected,
        )
    )
    return director, research_strategy, strategy, selected, production


@pytest.mark.asyncio
async def test_director_output_matches_schema() -> None:
    output = await DirectorAgent(_model_provider()).execute(
        DirectorInput(request_text="为新品咖啡做一条营销短视频")
    )

    assert DirectorOutput.model_validate(output.model_dump(mode="json")) == output
    assert output.workflow_type == "topic_to_video"


@pytest.mark.asyncio
async def test_strategy_outputs_exactly_three_options() -> None:
    _, _, strategy, *_ = await _production_inputs()

    assert len(strategy.strategy_options) == 3
    assert strategy.recommended_strategy_id in {
        option.strategy_id for option in strategy.strategy_options
    }


@pytest.mark.asyncio
async def test_reviewer_pass() -> None:
    director, _, _, selected, production = await _production_inputs()
    output = await ReviewerAgent(_model_provider()).execute(
        ReviewerInput(
            creative_brief=director.creative_brief,
            selected_strategy=selected,
            copywriting=production.copywriting,
            storyboard=production.storyboard,
            video_prompt=production.video_prompt,
        )
    )

    assert output.status is ReviewStatus.PASS
    assert output.issues == []


@pytest.mark.asyncio
async def test_reviewer_fail() -> None:
    director, _, _, selected, production = await _production_inputs()
    output = await ReviewerAgent(_model_provider("review_fail")).execute(
        ReviewerInput(
            creative_brief=director.creative_brief,
            selected_strategy=selected,
            copywriting=production.copywriting,
            storyboard=production.storyboard,
            video_prompt=production.video_prompt,
        )
    )

    assert output.status is ReviewStatus.FAIL
    assert output.issues
    assert output.return_to == "video_prompt"
