from pydantic import Field

from jhai_to_c.contracts.common import ContractModel, ProjectReference
from jhai_to_c.contracts.director import CreativeBrief
from jhai_to_c.contracts.production import (
    CopywritingOutput,
    ProductionCoordinatorOutput,
    ProductionPackageOutput,
    StoryboardOutput,
    VideoPromptOutput,
)
from jhai_to_c.contracts.strategy import StrategyOption
from jhai_to_c.prompts import PromptLoader
from jhai_to_c.providers.interfaces import AgentModelProvider

from .config import LEGACY_AGENT_CONFIGS, AgentConfig, AgentName
from .feedback import prompt_input_with_feedback
from .registry import build_default_agent_registry


class ProductionCoordinatorInput(ContractModel):
    creative_brief: CreativeBrief
    selected_strategy: StrategyOption
    references: list[ProjectReference] = Field(default_factory=list, max_length=20)


class ProductionInput(ContractModel):
    creative_brief: CreativeBrief
    selected_strategy: StrategyOption
    references: list[ProjectReference] = Field(default_factory=list, max_length=20)


class CopywriterInput(ContractModel):
    creative_brief: CreativeBrief
    selected_strategy: StrategyOption
    production_plan: ProductionCoordinatorOutput
    references: list[ProjectReference] = Field(default_factory=list, max_length=20)


class StoryboardAgentInput(ContractModel):
    creative_brief: CreativeBrief
    selected_strategy: StrategyOption
    production_plan: ProductionCoordinatorOutput
    copywriting: CopywritingOutput
    references: list[ProjectReference] = Field(default_factory=list, max_length=20)


class VideoPromptAgentInput(ContractModel):
    creative_brief: CreativeBrief
    selected_strategy: StrategyOption
    production_plan: ProductionCoordinatorOutput
    copywriting: CopywritingOutput
    storyboard: StoryboardOutput
    references: list[ProjectReference] = Field(default_factory=list, max_length=20)


class _SinglePromptProductionAgent:
    expected_name: AgentName
    input_schema: type[ContractModel]
    output_schema: type[ContractModel]

    def __init__(
        self,
        provider: AgentModelProvider,
        *,
        config: AgentConfig | None = None,
        system_prompt: str | None = None,
    ) -> None:
        resolved_config = config or LEGACY_AGENT_CONFIGS[self.expected_name]
        if resolved_config.name is not self.expected_name:
            raise ValueError(
                f"{type(self).__name__} requires the {self.expected_name.value} AgentConfig"
            )
        if len(resolved_config.prompt_names) != 1:
            raise ValueError(
                f"{self.expected_name.value} AgentConfig must declare exactly one prompt"
            )
        self.config = resolved_config
        self.system_prompt = system_prompt or PromptLoader().load(resolved_config.prompt_names[0])
        self.provider = provider

    async def _execute(
        self,
        input_data: ContractModel,
        *,
        node: str,
        feedback: str | None = None,
    ):
        result = await self.provider.generate_structured(
            system_prompt=self.system_prompt,
            input_data=prompt_input_with_feedback(input_data, feedback),
            output_model=self.output_schema,
            metadata={"agent": self.config.name.value, "node": node},
        )
        return result.output


class ProductionCoordinatorAgent(_SinglePromptProductionAgent):
    expected_name = AgentName.PRODUCTION_COORDINATOR
    input_schema = ProductionCoordinatorInput
    output_schema = ProductionCoordinatorOutput

    async def execute(
        self,
        input_data: ProductionCoordinatorInput,
        *,
        feedback: str | None = None,
    ) -> ProductionCoordinatorOutput:
        return await self._execute(
            input_data,
            node="production_coordinator",
            feedback=feedback,
        )


class CopywriterAgent(_SinglePromptProductionAgent):
    expected_name = AgentName.COPYWRITER_AGENT
    input_schema = CopywriterInput
    output_schema = CopywritingOutput

    async def execute(
        self,
        input_data: CopywriterInput,
        *,
        feedback: str | None = None,
    ) -> CopywritingOutput:
        return await self._execute(input_data, node="copywriting", feedback=feedback)


class StoryboardAgent(_SinglePromptProductionAgent):
    expected_name = AgentName.STORYBOARD_AGENT
    input_schema = StoryboardAgentInput
    output_schema = StoryboardOutput

    async def execute(
        self,
        input_data: StoryboardAgentInput,
        *,
        feedback: str | None = None,
    ) -> StoryboardOutput:
        return await self._execute(input_data, node="storyboard", feedback=feedback)


class VideoPromptAgent(_SinglePromptProductionAgent):
    expected_name = AgentName.VIDEO_PROMPT_AGENT
    input_schema = VideoPromptAgentInput
    output_schema = VideoPromptOutput

    async def execute(
        self,
        input_data: VideoPromptAgentInput,
        *,
        feedback: str | None = None,
    ) -> VideoPromptOutput:
        return await self._execute(input_data, node="video_prompt", feedback=feedback)


class ProductionAgent:
    input_schema = ProductionInput
    output_schema = ProductionPackageOutput

    def __init__(
        self,
        provider: AgentModelProvider,
        *,
        config: AgentConfig | None = None,
        system_prompt: str | None = None,
    ) -> None:
        resolved_config = config or build_default_agent_registry().get(AgentName.PRODUCTION)
        if resolved_config.name is not AgentName.PRODUCTION:
            raise ValueError("ProductionAgent requires the production AgentConfig")
        if len(resolved_config.prompt_names) != 1:
            raise ValueError("Production AgentConfig must declare exactly one prompt")
        self.config = resolved_config
        self.system_prompt = system_prompt or PromptLoader().load(resolved_config.prompt_names[0])
        self.provider = provider

    async def execute(
        self,
        input_data: ProductionInput,
        *,
        feedback: str | None = None,
    ) -> ProductionPackageOutput:
        result = await self.provider.generate_structured(
            system_prompt=self.system_prompt,
            input_data=prompt_input_with_feedback(input_data, feedback),
            output_model=self.output_schema,
            metadata={"agent": self.config.name.value, "node": "production"},
        )
        return result.output


# Compatibility aliases for imports of Phase B input type names.
CopywritingInput = CopywriterInput
StoryboardInput = StoryboardAgentInput
VideoPromptInput = VideoPromptAgentInput
