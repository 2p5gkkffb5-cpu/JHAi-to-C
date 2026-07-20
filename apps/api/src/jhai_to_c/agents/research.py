from pydantic import Field

from jhai_to_c.contracts.common import ContractModel, ProjectReference
from jhai_to_c.contracts.director import CreativeBrief
from jhai_to_c.contracts.research import ResearchOutput, ResearchStrategyOutput
from jhai_to_c.prompts import PromptLoader
from jhai_to_c.providers.interfaces import (
    AgentModelProvider,
    ResearchProvider,
    ResearchQuery,
)

from .config import AgentConfig, AgentName
from .feedback import prompt_input_with_feedback
from .registry import build_default_agent_registry


class ResearchInput(ContractModel):
    request_text: str = Field(min_length=1, max_length=5000)
    creative_brief: CreativeBrief
    references: list[ProjectReference] = Field(default_factory=list, max_length=20)


ResearchOutputSchema = ResearchOutput


class ResearchAgent:
    input_schema = ResearchInput
    output_schema = ResearchOutput

    def __init__(
        self,
        model_provider: AgentModelProvider,
        research_provider: ResearchProvider,
        *,
        config: AgentConfig | None = None,
        system_prompt: str | None = None,
    ) -> None:
        resolved_config = (
            config if config is not None else build_default_agent_registry().get(AgentName.RESEARCH)
        )
        if resolved_config.name is not AgentName.RESEARCH:
            raise ValueError("ResearchAgent requires the research AgentConfig")
        if len(resolved_config.prompt_names) != 1:
            raise ValueError("Research AgentConfig must declare exactly one prompt")

        self.config = resolved_config
        self.system_prompt = (
            system_prompt
            if system_prompt is not None
            else PromptLoader().load(resolved_config.prompt_names[0])
        )
        self.model_provider = model_provider
        self.research_provider = research_provider

    async def execute(
        self,
        input_data: ResearchInput,
        *,
        feedback: str | None = None,
    ) -> ResearchOutput:
        brief = input_data.creative_brief
        queries = [
            ResearchQuery(
                query=f"{brief.product} 的目标受众痛点与购买动机",
                context={"platform": brief.platform, "audience": brief.target_audience},
            ),
            ResearchQuery(
                query=f"{brief.platform} 平台 {brief.industry} 营销短视频内容趋势",
                context={"duration_seconds": brief.duration_seconds},
            ),
            ResearchQuery(
                query=f"{brief.product} 同类内容的常见叙事结构与风险",
                context={"goal": brief.goal},
            ),
        ]
        provider_result = await self.research_provider.search(queries=queries)
        prompt_input = prompt_input_with_feedback(input_data, feedback)
        prompt_input["research_provider"] = provider_result.provider
        prompt_input["research_is_mock"] = provider_result.is_mock
        prompt_input["research_sources"] = [
            source.model_dump(mode="json") for source in provider_result.sources
        ]
        result = await self.model_provider.generate_structured(
            system_prompt=self.system_prompt,
            input_data=prompt_input,
            output_model=self.output_schema,
            metadata={
                "agent": self.config.name.value,
                "research_provider": provider_result.provider,
                "research_is_mock": provider_result.is_mock,
            },
        )
        return result.output


class ResearchStrategyAgent(ResearchAgent):
    """Searches first, then returns research and three strategies in one LLM call."""

    output_schema = ResearchStrategyOutput

    async def execute(
        self,
        input_data: ResearchInput,
        *,
        feedback: str | None = None,
    ) -> ResearchStrategyOutput:
        brief = input_data.creative_brief
        queries = [
            ResearchQuery(
                query=f"{brief.product} 的目标受众痛点与购买动机",
                context={"platform": brief.platform, "audience": brief.target_audience},
            ),
            ResearchQuery(
                query=f"{brief.platform} 平台 {brief.industry} 营销短视频内容趋势",
                context={"duration_seconds": brief.duration_seconds},
            ),
            ResearchQuery(
                query=f"{brief.product} 同类内容的常见叙事结构与风险",
                context={"goal": brief.goal},
            ),
        ]
        provider_result = await self.research_provider.search(queries=queries)
        prompt_input = prompt_input_with_feedback(input_data, feedback)
        prompt_input["research_provider"] = provider_result.provider
        prompt_input["research_is_mock"] = provider_result.is_mock
        prompt_input["research_sources"] = [
            source.model_dump(mode="json") for source in provider_result.sources
        ]
        result = await self.model_provider.generate_structured(
            system_prompt=self.system_prompt,
            input_data=prompt_input,
            output_model=self.output_schema,
            metadata={
                "agent": self.config.name.value,
                "node": "research",
                "research_provider": provider_result.provider,
                "research_is_mock": provider_result.is_mock,
            },
        )
        return result.output


async def execute(
    input_data: ResearchInput,
    model_provider: AgentModelProvider,
    research_provider: ResearchProvider,
) -> ResearchOutput:
    return await ResearchAgent(model_provider, research_provider).execute(input_data)
