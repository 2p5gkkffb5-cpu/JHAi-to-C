import pytest

from jhai_to_c.contracts.director import DirectorOutput
from jhai_to_c.providers.mock import (
    DeterministicMockAgentModelProvider,
    MockProviderControl,
)
from jhai_to_c.workflow.runtime_contracts import (
    AgentOutputExtractionError,
    extract_agent_output,
    parse_agent_run_output,
)


@pytest.mark.asyncio
async def test_output_extractor_persists_only_model_body_and_reads_legacy_envelope() -> None:
    provider = DeterministicMockAgentModelProvider(MockProviderControl(latency_ms=0))
    generated = await provider.generate_structured(
        system_prompt="test",
        input_data={"request_text": "生成短视频"},
        output_model=DirectorOutput,
    )
    body = generated.output.model_dump(mode="json")
    task_result = {
        "director": body,
        "creative_brief": body["creative_brief"],
        "current_node": "director",
        "completed_nodes": ["director"],
    }

    assert extract_agent_output("director", task_result) == body
    assert parse_agent_run_output("director", body).model_dump(mode="json") == body
    assert parse_agent_run_output("director", task_result).model_dump(mode="json") == body


@pytest.mark.parametrize("result", [{}, {"director": []}, None])
def test_output_extractor_fails_closed(result) -> None:
    with pytest.raises(AgentOutputExtractionError):
        extract_agent_output("director", result)
