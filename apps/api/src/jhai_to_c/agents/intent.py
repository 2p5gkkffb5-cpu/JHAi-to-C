import logging

from jhai_to_c.contracts.intent import (
    IntentDecision,
    IntentRoutingInput,
    RequestedMode,
    TaskIntent,
)
from jhai_to_c.prompts import PromptLoader
from jhai_to_c.providers.interfaces import AgentModelProvider
from jhai_to_c.providers.real.llm import RealLLMProviderError

logger = logging.getLogger(__name__)

INTENT_ROUTER_TIMEOUT_SECONDS = 20


class IntentRouterAgent:
    input_schema = IntentRoutingInput
    output_schema = IntentDecision

    def __init__(
        self,
        provider: AgentModelProvider,
        *,
        system_prompt: str | None = None,
    ) -> None:
        self.provider = provider
        self.system_prompt = system_prompt or PromptLoader().load("intent_router")

    async def execute(self, input_data: IntentRoutingInput) -> IntentDecision:
        if input_data.requested_mode is not RequestedMode.AUTO:
            return IntentDecision(
                intent=TaskIntent(input_data.requested_mode.value),
                confidence=1,
                reason_code="explicit_mode",
            )

        try:
            result = await self.provider.generate_structured(
                system_prompt=self.system_prompt,
                input_data=input_data.model_dump(mode="json"),
                output_model=self.output_schema,
                timeout_seconds=INTENT_ROUTER_TIMEOUT_SECONDS,
                metadata={"component": "intent_router", "node": "intent_router"},
            )
        except RealLLMProviderError as exc:
            logger.warning(
                "Intent routing provider failed; defaulting to the full creation workflow",
                extra={"provider_error_type": type(exc).__name__},
            )
            return IntentDecision(
                intent=TaskIntent.FULL_CREATION,
                confidence=0,
                reason_code="ambiguous_default",
            )
        return result.output
