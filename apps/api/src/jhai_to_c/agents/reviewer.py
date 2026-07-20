from pydantic import Field

from jhai_to_c.contracts.common import ContractModel, ProjectReference
from jhai_to_c.contracts.director import CreativeBrief
from jhai_to_c.contracts.production import (
    CopywritingOutput,
    StoryboardOutput,
    VideoPromptOutput,
)
from jhai_to_c.contracts.review import ReviewerOutput
from jhai_to_c.contracts.strategy import StrategyOption
from jhai_to_c.prompts import PromptLoader
from jhai_to_c.providers.interfaces import AgentModelProvider

from .config import LEGACY_AGENT_CONFIGS, AgentConfig, AgentName
from .feedback import prompt_input_with_feedback


class ReviewerInput(ContractModel):
    creative_brief: CreativeBrief
    selected_strategy: StrategyOption
    copywriting: CopywritingOutput
    storyboard: StoryboardOutput
    video_prompt: VideoPromptOutput
    references: list[ProjectReference] = Field(default_factory=list, max_length=20)


ReviewerOutputSchema = ReviewerOutput


class ReviewerAgent:
    input_schema = ReviewerInput
    output_schema = ReviewerOutput

    def __init__(
        self,
        provider: AgentModelProvider,
        *,
        config: AgentConfig | None = None,
        system_prompt: str | None = None,
    ) -> None:
        resolved_config = config or LEGACY_AGENT_CONFIGS[AgentName.REVIEWER]
        if resolved_config.name is not AgentName.REVIEWER:
            raise ValueError("ReviewerAgent requires the reviewer AgentConfig")
        if len(resolved_config.prompt_names) != 1:
            raise ValueError("Reviewer AgentConfig must declare exactly one prompt")

        self.config = resolved_config
        self.system_prompt = (
            system_prompt
            if system_prompt is not None
            else PromptLoader().load(resolved_config.prompt_names[0])
        )
        self.provider = provider

    async def execute(
        self,
        input_data: ReviewerInput,
        *,
        feedback: str | None = None,
    ) -> ReviewerOutput:
        result = await self.provider.generate_structured(
            system_prompt=self.system_prompt,
            input_data=prompt_input_with_feedback(input_data, feedback),
            output_model=self.output_schema,
            metadata={"agent": self.config.name.value},
        )
        return result.output


async def execute(input_data: ReviewerInput, provider: AgentModelProvider) -> ReviewerOutput:
    return await ReviewerAgent(provider).execute(input_data)
