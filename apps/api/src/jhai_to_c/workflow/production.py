from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from jhai_to_c.agents.production import (
    CopywriterAgent,
    CopywriterInput,
    ProductionCoordinatorAgent,
    ProductionCoordinatorInput,
    ProductionInput,
    StoryboardAgent,
    StoryboardAgentInput,
    VideoPromptAgent,
    VideoPromptAgentInput,
)
from jhai_to_c.contracts.common import ContractModel, ProjectReference
from jhai_to_c.contracts.director import CreativeBrief
from jhai_to_c.contracts.production import (
    CopywritingOutput,
    ProductionCoordinatorOutput,
    ProductionPackageOutput,
    StoryboardOutput,
    VideoPromptOutput,
)
from jhai_to_c.contracts.strategy import StrategyOption, StrategyOutput

from .errors import InvalidReferenceSubsetError
from .nodes import (
    COPYWRITING_APPROVAL_NODE,
    COPYWRITING_NODE,
    STORYBOARD_APPROVAL_NODE,
    STORYBOARD_NODE,
    VIDEO_PROMPT_APPROVAL_NODE,
    VIDEO_PROMPT_NODE,
    AgentApprovalNode,
    _node_update,
)

PRODUCTION_COORDINATOR_NODE = "production_coordinator"
PRODUCTION_COORDINATOR_APPROVAL_NODE = "production_coordinator_approval"

VIDEO_PROMPT_LINE_LABELS = (
    "镜头类型",
    "主体",
    "场景",
    "连续动作",
    "微表情",
    "符合场景的微动作",
    "服饰因动作产生的物理反应",
    "口播",
    "符合人物身份、场景细节的语气",
    "镜头运动",
    "光线氛围",
    "风格",
    "细节",
    "时长",
)


class ProductionInputState(TypedDict, total=False):
    creative_brief: dict[str, Any]
    strategies: dict[str, Any]
    selected_strategy_id: str
    references: list[dict[str, Any]]
    current_node: str
    completed_nodes: list[str]
    provider_usage: dict[str, dict[str, Any]]
    agent_feedback: dict[str, str]
    agent_attempts: dict[str, int]
    approval_action: str
    approval_node: str


class ProductionState(ProductionInputState, total=False):
    production_plan: dict[str, Any]
    copywriting: dict[str, Any]
    storyboard: dict[str, Any]
    video_prompt: dict[str, Any]


class ProductionOutputState(TypedDict, total=False):
    copywriting: dict[str, Any]
    storyboard: dict[str, Any]
    video_prompt: dict[str, Any]
    current_node: str
    completed_nodes: list[str]
    provider_usage: dict[str, dict[str, Any]]


def _references(state: Mapping[str, Any]) -> list[ProjectReference]:
    return [ProjectReference.model_validate(item) for item in state.get("references", [])]


def _selected_strategy(state: Mapping[str, Any]) -> StrategyOption:
    strategies = StrategyOutput.model_validate(state["strategies"])
    strategy_id = state.get("selected_strategy_id", strategies.recommended_strategy_id)
    selected = next(
        (option for option in strategies.strategy_options if option.strategy_id == strategy_id),
        None,
    )
    if selected is None:
        raise ValueError(f"Selected strategy does not exist: {strategy_id}")
    return selected


def _filtered_references(state: Mapping[str, Any]) -> list[ProjectReference]:
    references = _references(state)
    plan = ProductionCoordinatorOutput.model_validate(state["production_plan"])
    allowed_ids = set(plan.allowed_reference_ids)
    return [reference for reference in references if reference.id in allowed_ids]


def _feedback(state: Mapping[str, Any], node_name: str) -> str | None:
    feedback = state.get("agent_feedback", {})
    if not isinstance(feedback, Mapping):
        return None
    value = feedback.get(node_name)
    return value if isinstance(value, str) and value else None


def _increment_attempt(state: Mapping[str, Any], node_name: str) -> dict[str, int]:
    current = state.get("agent_attempts", {})
    attempts = dict(current) if isinstance(current, Mapping) else {}
    attempts[node_name] = int(attempts.get(node_name, 0)) + 1
    return attempts


def _route_approval(state: Mapping[str, Any]) -> str:
    action = state.get("approval_action")
    if action not in {"approve", "retry"}:
        raise ValueError(f"Unknown Agent approval action: {action}")
    return str(action)


def project_coordinator_input(state: Mapping[str, Any]) -> ProductionCoordinatorInput:
    return ProductionCoordinatorInput(
        creative_brief=CreativeBrief.model_validate(state["creative_brief"]),
        selected_strategy=_selected_strategy(state),
        references=_references(state),
    )


def project_production_input(state: Mapping[str, Any]) -> ProductionInput:
    return ProductionInput(
        creative_brief=CreativeBrief.model_validate(state["creative_brief"]),
        selected_strategy=_selected_strategy(state),
        references=_references(state),
    )


def project_copywriter_input(state: Mapping[str, Any]) -> CopywriterInput:
    return CopywriterInput(
        creative_brief=CreativeBrief.model_validate(state["creative_brief"]),
        selected_strategy=_selected_strategy(state),
        production_plan=ProductionCoordinatorOutput.model_validate(state["production_plan"]),
        references=_filtered_references(state),
    )


def project_storyboard_input(state: Mapping[str, Any]) -> StoryboardAgentInput:
    return StoryboardAgentInput(
        creative_brief=CreativeBrief.model_validate(state["creative_brief"]),
        selected_strategy=_selected_strategy(state),
        production_plan=ProductionCoordinatorOutput.model_validate(state["production_plan"]),
        copywriting=CopywritingOutput.model_validate(state["copywriting"]),
        references=_filtered_references(state),
    )


def project_video_prompt_input(state: Mapping[str, Any]) -> VideoPromptAgentInput:
    return VideoPromptAgentInput(
        creative_brief=CreativeBrief.model_validate(state["creative_brief"]),
        selected_strategy=_selected_strategy(state),
        production_plan=ProductionCoordinatorOutput.model_validate(state["production_plan"]),
        copywriting=CopywritingOutput.model_validate(state["copywriting"]),
        storyboard=StoryboardOutput.model_validate(state["storyboard"]),
        references=_filtered_references(state),
    )


AgentInputProjector = Callable[[Mapping[str, Any]], ContractModel]
PRODUCTION_INPUT_PROJECTORS: dict[str, AgentInputProjector] = {
    PRODUCTION_COORDINATOR_NODE: project_coordinator_input,
    COPYWRITING_NODE: project_copywriter_input,
    STORYBOARD_NODE: project_storyboard_input,
    VIDEO_PROMPT_NODE: project_video_prompt_input,
}


def _duplicates(values: list[str]) -> list[str]:
    seen: set[str] = set()
    duplicates: list[str] = []
    for value in values:
        if value in seen and value not in duplicates:
            duplicates.append(value)
        seen.add(value)
    return duplicates


def validate_reference_subset(
    node_name: str,
    output: ContractModel,
    agent_input: ContractModel,
) -> None:
    if node_name == PRODUCTION_COORDINATOR_NODE:
        coordinator_output = ProductionCoordinatorOutput.model_validate(output)
        coordinator_input = ProductionCoordinatorInput.model_validate(agent_input)
        selected_ids = coordinator_output.allowed_reference_ids
        allowed_ids = [reference.id for reference in coordinator_input.references]
        duplicate_ids = _duplicates(selected_ids)
        internal_agent = "production_coordinator"
    else:
        input_payload = agent_input.model_dump(mode="json")
        plan = ProductionCoordinatorOutput.model_validate(input_payload["production_plan"])
        input_ids = [
            reference.id
            for reference in [
                ProjectReference.model_validate(item) for item in input_payload["references"]
            ]
        ]
        allowed_ids = [item for item in plan.allowed_reference_ids if item in set(input_ids)]
        duplicate_ids = []
        internal_agent = {
            COPYWRITING_NODE: "copywriter_agent",
            STORYBOARD_NODE: "storyboard_agent",
            VIDEO_PROMPT_NODE: "video_prompt_agent",
        }[node_name]
        if node_name == COPYWRITING_NODE:
            selected_ids = [
                binding.reference_id
                for binding in CopywritingOutput.model_validate(output).fact_bindings
            ]
        elif node_name == STORYBOARD_NODE:
            selected_ids = [
                reference_id
                for shot in StoryboardOutput.model_validate(output).shots
                for reference_id in shot.reference_ids
            ]
        else:
            selected_ids = VideoPromptOutput.model_validate(output).reference_ids

    allowed = set(allowed_ids)
    invalid_ids = list(dict.fromkeys(item for item in selected_ids if item not in allowed))
    if invalid_ids or duplicate_ids:
        raise InvalidReferenceSubsetError(
            internal_agent=internal_agent,
            invalid_ids=invalid_ids,
            duplicate_ids=duplicate_ids,
            allowed_ids=allowed_ids,
        )


def validate_video_prompt_format(output: VideoPromptOutput) -> None:
    if "+" in output.prompt:
        raise ValueError("Video prompt must use line breaks instead of plus separators")
    lines = output.prompt.strip().splitlines()
    if len(lines) != len(VIDEO_PROMPT_LINE_LABELS):
        raise ValueError(
            "Video prompt must contain exactly 14 non-empty compact plain-text lines"
        )
    for line, label in zip(lines, VIDEO_PROMPT_LINE_LABELS, strict=True):
        prefix = f"[{label}]"
        if not line.startswith(prefix) or not line.removeprefix(prefix).strip():
            raise ValueError(
                f"Video prompt line must start with {prefix} and contain a value"
            )


def validate_production_package(
    output: ProductionPackageOutput,
    agent_input: ProductionInput,
) -> None:
    validate_video_prompt_format(output.video_prompt)
    coordinator_input = ProductionCoordinatorInput(
        creative_brief=agent_input.creative_brief,
        selected_strategy=agent_input.selected_strategy,
        references=agent_input.references,
    )
    validate_reference_subset(
        PRODUCTION_COORDINATOR_NODE,
        output.production_plan,
        coordinator_input,
    )
    allowed_ids = set(output.production_plan.allowed_reference_ids)
    references = [item for item in agent_input.references if item.id in allowed_ids]
    copywriter_input = CopywriterInput(
        creative_brief=agent_input.creative_brief,
        selected_strategy=agent_input.selected_strategy,
        production_plan=output.production_plan,
        references=references,
    )
    validate_reference_subset(COPYWRITING_NODE, output.copywriting, copywriter_input)
    storyboard_input = StoryboardAgentInput(
        creative_brief=agent_input.creative_brief,
        selected_strategy=agent_input.selected_strategy,
        production_plan=output.production_plan,
        copywriting=output.copywriting,
        references=references,
    )
    validate_reference_subset(STORYBOARD_NODE, output.storyboard, storyboard_input)
    video_prompt_input = VideoPromptAgentInput(
        creative_brief=agent_input.creative_brief,
        selected_strategy=agent_input.selected_strategy,
        production_plan=output.production_plan,
        copywriting=output.copywriting,
        storyboard=output.storyboard,
        references=references,
    )
    validate_reference_subset(VIDEO_PROMPT_NODE, output.video_prompt, video_prompt_input)


@dataclass(slots=True)
class ProductionCoordinatorNode:
    agent: ProductionCoordinatorAgent

    async def __call__(self, state: ProductionState) -> ProductionState:
        agent_input = project_coordinator_input(state)
        output = await self.agent.execute(
            agent_input,
            feedback=_feedback(state, PRODUCTION_COORDINATOR_NODE),
        )
        validate_reference_subset(PRODUCTION_COORDINATOR_NODE, output, agent_input)
        return {
            "production_plan": output.model_dump(mode="json"),
            "agent_attempts": _increment_attempt(state, PRODUCTION_COORDINATOR_NODE),
        }


@dataclass(slots=True)
class CopywritingNode:
    agent: CopywriterAgent

    async def __call__(self, state: ProductionState) -> ProductionState:
        agent_input = project_copywriter_input(state)
        output = await self.agent.execute(
            agent_input,
            feedback=_feedback(state, COPYWRITING_NODE),
        )
        validate_reference_subset(COPYWRITING_NODE, output, agent_input)
        return _node_update(
            state,
            node_name=COPYWRITING_NODE,
            provider=self.agent.provider.provider_name,
            is_mock=self.agent.provider.is_mock,
            copywriting=output.model_dump(mode="json"),
        )


@dataclass(slots=True)
class StoryboardNode:
    agent: StoryboardAgent

    async def __call__(self, state: ProductionState) -> ProductionState:
        agent_input = project_storyboard_input(state)
        output = await self.agent.execute(
            agent_input,
            feedback=_feedback(state, STORYBOARD_NODE),
        )
        validate_reference_subset(STORYBOARD_NODE, output, agent_input)
        return _node_update(
            state,
            node_name=STORYBOARD_NODE,
            provider=self.agent.provider.provider_name,
            is_mock=self.agent.provider.is_mock,
            storyboard=output.model_dump(mode="json"),
        )


@dataclass(slots=True)
class VideoPromptNode:
    agent: VideoPromptAgent

    async def __call__(self, state: ProductionState) -> ProductionState:
        agent_input = project_video_prompt_input(state)
        output = await self.agent.execute(
            agent_input,
            feedback=_feedback(state, VIDEO_PROMPT_NODE),
        )
        validate_video_prompt_format(output)
        validate_reference_subset(VIDEO_PROMPT_NODE, output, agent_input)
        return _node_update(
            state,
            node_name=VIDEO_PROMPT_NODE,
            provider=self.agent.provider.provider_name,
            is_mock=self.agent.provider.is_mock,
            video_prompt=output.model_dump(mode="json"),
        )


def build_production_subgraph(
    coordinator: ProductionCoordinatorAgent,
    copywriter: CopywriterAgent,
    storyboard: StoryboardAgent,
    video_prompt: VideoPromptAgent,
    *,
    require_agent_approval: bool = False,
):
    graph = StateGraph(
        ProductionState,
        input_schema=ProductionInputState,
        output_schema=ProductionOutputState,
    )
    graph.add_node(PRODUCTION_COORDINATOR_NODE, ProductionCoordinatorNode(coordinator))
    graph.add_node(COPYWRITING_NODE, CopywritingNode(copywriter))
    graph.add_node(STORYBOARD_NODE, StoryboardNode(storyboard))
    graph.add_node(VIDEO_PROMPT_NODE, VideoPromptNode(video_prompt))
    graph.add_edge(START, PRODUCTION_COORDINATOR_NODE)
    if require_agent_approval:
        graph.add_node(
            PRODUCTION_COORDINATOR_APPROVAL_NODE,
            AgentApprovalNode(
                node_name=PRODUCTION_COORDINATOR_NODE,
                agent_name="production_coordinator",
            ),
        )
        graph.add_node(
            COPYWRITING_APPROVAL_NODE,
            AgentApprovalNode(
                node_name=COPYWRITING_NODE,
                agent_name="copywriter_agent",
                artifact_type="copywriting",
            ),
        )
        graph.add_node(
            STORYBOARD_APPROVAL_NODE,
            AgentApprovalNode(
                node_name=STORYBOARD_NODE,
                agent_name="storyboard_agent",
                artifact_type="storyboard",
            ),
        )
        graph.add_node(
            VIDEO_PROMPT_APPROVAL_NODE,
            AgentApprovalNode(
                node_name=VIDEO_PROMPT_NODE,
                agent_name="video_prompt_agent",
                artifact_type="video_prompt",
            ),
        )
        graph.add_edge(PRODUCTION_COORDINATOR_NODE, PRODUCTION_COORDINATOR_APPROVAL_NODE)
        graph.add_conditional_edges(
            PRODUCTION_COORDINATOR_APPROVAL_NODE,
            _route_approval,
            {"approve": COPYWRITING_NODE, "retry": PRODUCTION_COORDINATOR_NODE},
        )
        graph.add_edge(COPYWRITING_NODE, COPYWRITING_APPROVAL_NODE)
        graph.add_conditional_edges(
            COPYWRITING_APPROVAL_NODE,
            _route_approval,
            {"approve": STORYBOARD_NODE, "retry": COPYWRITING_NODE},
        )
        graph.add_edge(STORYBOARD_NODE, STORYBOARD_APPROVAL_NODE)
        graph.add_conditional_edges(
            STORYBOARD_APPROVAL_NODE,
            _route_approval,
            {"approve": VIDEO_PROMPT_NODE, "retry": STORYBOARD_NODE},
        )
        graph.add_edge(VIDEO_PROMPT_NODE, VIDEO_PROMPT_APPROVAL_NODE)
        graph.add_conditional_edges(
            VIDEO_PROMPT_APPROVAL_NODE,
            _route_approval,
            {"approve": END, "retry": VIDEO_PROMPT_NODE},
        )
    else:
        graph.add_edge(PRODUCTION_COORDINATOR_NODE, COPYWRITING_NODE)
        graph.add_edge(COPYWRITING_NODE, STORYBOARD_NODE)
        graph.add_edge(STORYBOARD_NODE, VIDEO_PROMPT_NODE)
        graph.add_edge(VIDEO_PROMPT_NODE, END)
    return graph.compile(name="production_subgraph")
