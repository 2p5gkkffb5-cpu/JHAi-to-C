from pydantic import Field

from jhai_to_c.contracts.common import ContractModel, ProjectReference
from jhai_to_c.contracts.director import CreativeBrief
from jhai_to_c.contracts.packaging import BrandPackagingOutput
from jhai_to_c.contracts.strategy import StrategyOption
from jhai_to_c.prompts import PromptLoader
from jhai_to_c.providers.interfaces import AgentModelProvider

from .feedback import prompt_input_with_feedback


class BrandPackagingInput(ContractModel):
    request_text: str = Field(min_length=1, max_length=5000)
    creative_brief: CreativeBrief
    selected_strategy: StrategyOption
    references: list[ProjectReference] = Field(default_factory=list, max_length=20)


class BrandPackagingAgent:
    input_schema = BrandPackagingInput
    output_schema = BrandPackagingOutput

    def __init__(
        self,
        provider: AgentModelProvider,
        *,
        system_prompt: str | None = None,
    ) -> None:
        self.provider = provider
        self.system_prompt = system_prompt or PromptLoader().load("brand_packaging")

    async def execute(
        self,
        input_data: BrandPackagingInput,
        *,
        feedback: str | None = None,
    ) -> BrandPackagingOutput:
        result = await self.provider.generate_structured(
            system_prompt=self.system_prompt,
            input_data=prompt_input_with_feedback(input_data, feedback),
            output_model=self.output_schema,
            metadata={"agent": "brand_packaging", "node": "brand_packaging"},
        )
        return result.output

