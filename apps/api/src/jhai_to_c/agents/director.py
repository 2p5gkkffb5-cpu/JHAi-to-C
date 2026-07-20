from typing import Any, Literal

from pydantic import Field

from jhai_to_c.contracts.common import ContractModel, ProjectReference
from jhai_to_c.contracts.director import DirectorOutput
from jhai_to_c.contracts.intent import RequestedMode
from jhai_to_c.prompts import PromptLoader
from jhai_to_c.providers.interfaces import AgentModelProvider

from .config import AgentConfig, AgentName
from .feedback import prompt_input_with_feedback
from .registry import build_default_agent_registry


class DirectorInput(ContractModel):
    request_text: str = Field(min_length=1, max_length=5000)
    references: list[ProjectReference] = Field(default_factory=list, max_length=20)
    blueprint: dict[str, Any] | None = None
    target_platform: str = Field(default="douyin", min_length=1, max_length=50)
    duration_seconds: int = Field(default=20, ge=5, le=180)
    aspect_ratio: Literal["9:16", "16:9", "1:1"] = "9:16"
    requested_mode: RequestedMode = RequestedMode.FULL_CREATION


DirectorOutputSchema = DirectorOutput


class DirectorAgent:
    input_schema = DirectorInput
    output_schema = DirectorOutput

    def __init__(
        self,
        provider: AgentModelProvider,
        *,
        config: AgentConfig | None = None,
        system_prompt: str | None = None,
    ) -> None:
        resolved_config = (
            config
            if config is not None
            else build_default_agent_registry().get(AgentName.SUPERVISOR)
        )
        if resolved_config.name is not AgentName.SUPERVISOR:
            raise ValueError("DirectorAgent requires the supervisor AgentConfig")
        if len(resolved_config.prompt_names) != 1:
            raise ValueError("Supervisor AgentConfig must declare exactly one prompt")

        self.config = resolved_config
        self.system_prompt = (
            system_prompt
            if system_prompt is not None
            else PromptLoader().load(resolved_config.prompt_names[0])
        )
        self.provider = provider

    async def execute(
        self,
        input_data: DirectorInput,
        *,
        feedback: str | None = None,
    ) -> DirectorOutput:
        result = await self.provider.generate_structured(
            system_prompt=self.system_prompt,
            input_data=prompt_input_with_feedback(input_data, feedback),
            output_model=self.output_schema,
            metadata={"agent": self.config.name.value, "node": "director"},
        )
        return result.output


async def execute(input_data: DirectorInput, provider: AgentModelProvider) -> DirectorOutput:
    return await DirectorAgent(provider).execute(input_data)
