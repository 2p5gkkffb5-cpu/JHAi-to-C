from pydantic import Field

from jhai_to_c.contracts.common import ContractModel, ProjectReference
from jhai_to_c.contracts.director import CreativeBrief
from jhai_to_c.contracts.research import ResearchOutput
from jhai_to_c.contracts.strategy import StrategyOutput
from jhai_to_c.prompts import PromptLoader
from jhai_to_c.providers.interfaces import AgentModelProvider

from .config import LEGACY_AGENT_CONFIGS, AgentConfig, AgentName
from .feedback import prompt_input_with_feedback


class StrategyInput(ContractModel):
    creative_brief: CreativeBrief
    research: ResearchOutput
    references: list[ProjectReference] = Field(default_factory=list, max_length=20)


StrategyOutputSchema = StrategyOutput


class StrategyAgent:
    input_schema = StrategyInput
    output_schema = StrategyOutput

    def __init__(
        self,
        provider: AgentModelProvider,
        *,
        config: AgentConfig | None = None,
        system_prompt: str | None = None,
    ) -> None:
        resolved_config = config or LEGACY_AGENT_CONFIGS[AgentName.STRATEGY]
        if resolved_config.name is not AgentName.STRATEGY:
            raise ValueError("StrategyAgent requires the strategy AgentConfig")
        if len(resolved_config.prompt_names) != 1:
            raise ValueError("Strategy AgentConfig must declare exactly one prompt")

        self.config = resolved_config
        self.system_prompt = (
            system_prompt
            if system_prompt is not None
            else PromptLoader().load(resolved_config.prompt_names[0])
        )
        self.provider = provider

    async def execute(
        self,
        input_data: StrategyInput,
        *,
        feedback: str | None = None,
    ) -> StrategyOutput:
        result = await self.provider.generate_structured(
            system_prompt=self.system_prompt,
            input_data=prompt_input_with_feedback(input_data, feedback),
            output_model=self.output_schema,
            metadata={"agent": self.config.name.value},
        )
        return result.output


async def execute(input_data: StrategyInput, provider: AgentModelProvider) -> StrategyOutput:
    return await StrategyAgent(provider).execute(input_data)
