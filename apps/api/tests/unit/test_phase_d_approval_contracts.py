import pytest
from pydantic import ValidationError

from jhai_to_c.contracts import AgentDecisionRequest


@pytest.mark.parametrize(
    "payload",
    [
        {"node_name": "director", "action": "approve"},
        {
            "node_name": "research",
            "action": "retry",
            "feedback": "请补充更具体的竞品数据",
        },
        {
            "node_name": "research",
            "action": "approve",
            "strategy_id": "strategy-scene",
        },
        {
            "node_name": "research",
            "action": "retry",
            "feedback": "请换一个更突出产品卖点的方向",
        },
        {"node_name": "production", "action": "approve"},
    ],
)
def test_agent_decision_request_accepts_supported_decisions(payload: dict[str, str]) -> None:
    decision = AgentDecisionRequest.model_validate(payload)

    assert decision.model_dump(exclude_none=True) == payload


@pytest.mark.parametrize(
    "payload",
    [
        {"node_name": "research", "action": "approve"},
        {"node_name": "research", "action": "approve", "strategy_id": None},
        {"node_name": "research", "action": "approve", "strategy_id": "   "},
    ],
)
def test_strategy_approval_requires_a_non_empty_strategy_id(
    payload: dict[str, str | None],
) -> None:
    with pytest.raises(ValidationError):
        AgentDecisionRequest.model_validate(payload)


@pytest.mark.parametrize(
    "payload",
    [
        {
            "node_name": "research",
            "action": "retry",
            "strategy_id": "strategy-scene",
        },
        {
            "node_name": "director",
            "action": "approve",
            "strategy_id": "strategy-scene",
        },
        {
            "node_name": "production",
            "action": "retry",
            "strategy_id": "strategy-scene",
        },
    ],
)
def test_strategy_id_is_rejected_outside_strategy_approval(payload: dict[str, str]) -> None:
    with pytest.raises(
        ValidationError,
        match="strategy_id is only allowed when approving research strategy",
    ):
        AgentDecisionRequest.model_validate(payload)


@pytest.mark.parametrize(
    "payload",
    [
        {"node_name": "unknown", "action": "approve"},
        {"node_name": "director", "action": "continue"},
        {"node_name": "director", "action": "retry", "feedback": "   "},
        {"node_name": "director", "action": "approve", "unexpected": True},
    ],
)
def test_agent_decision_request_rejects_invalid_or_extra_fields(payload: dict) -> None:
    with pytest.raises(ValidationError):
        AgentDecisionRequest.model_validate(payload)
