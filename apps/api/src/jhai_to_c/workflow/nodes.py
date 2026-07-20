from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from langgraph.types import interrupt

from jhai_to_c.agents.director import DirectorAgent, DirectorInput
from jhai_to_c.agents.intent import IntentRouterAgent
from jhai_to_c.agents.packaging import BrandPackagingAgent, BrandPackagingInput
from jhai_to_c.agents.production import ProductionAgent, ProductionInput
from jhai_to_c.agents.research import ResearchInput, ResearchStrategyAgent
from jhai_to_c.agents.reviewer import ReviewerAgent, ReviewerInput
from jhai_to_c.agents.strategy import StrategyAgent, StrategyInput
from jhai_to_c.agents.video_clone import (
    VideoCloneMappingAgent,
    VideoCloneMappingInput,
    VideoClonePromptAgent,
    VideoClonePromptInput,
)
from jhai_to_c.contracts.common import ProjectReference
from jhai_to_c.contracts.director import CreativeBrief
from jhai_to_c.contracts.intent import IntentRoutingInput, RequestedMode, TaskIntent
from jhai_to_c.contracts.production import (
    CopywritingOutput,
    StoryboardOutput,
    VideoPromptOutput,
)
from jhai_to_c.contracts.research import ResearchOutput
from jhai_to_c.contracts.strategy import StrategyOption, StrategyOutput
from jhai_to_c.contracts.video import (
    VideoGenerationRequest,
    VideoTask,
    VideoTaskStatus,
)
from jhai_to_c.contracts.video_clone import (
    VideoCloneAnalysisOutput,
    VideoCloneAnalysisRequest,
    VideoCloneMappingOutput,
    VideoClonePromptOutput,
    VideoCloneReviewRequest,
)
from jhai_to_c.providers.interfaces import VideoProvider, VideoUnderstandingProvider

from .errors import CapabilityUnavailableError, InvalidReferenceSubsetError
from .state import ContentWorkflowState

VideoReferenceResolver = Callable[[str], Awaitable[str | None]]

DIRECTOR_NODE = "director"
INTENT_ROUTER_NODE = "intent_router"
IMAGE_GENERATION_NODE = "image_generation"
DIRECTOR_APPROVAL_NODE = "director_approval"
RESEARCH_NODE = "research"
RESEARCH_APPROVAL_NODE = "research_approval"
PRODUCTION_NODE = "production"
PRODUCTION_APPROVAL_NODE = "production_approval"
BRAND_PACKAGING_NODE = "brand_packaging"
BRAND_PACKAGING_APPROVAL_NODE = "brand_packaging_approval"
STRATEGY_NODE = "strategy"
STRATEGY_APPROVAL_NODE = "strategy_approval"
COPYWRITING_NODE = "copywriting"
COPYWRITING_APPROVAL_NODE = "copywriting_approval"
STORYBOARD_NODE = "storyboard"
STORYBOARD_APPROVAL_NODE = "storyboard_approval"
VIDEO_PROMPT_NODE = "video_prompt"
VIDEO_PROMPT_APPROVAL_NODE = "video_prompt_approval"
REVIEWER_NODE = "reviewer"
REVIEWER_APPROVAL_NODE = "reviewer_approval"
VIDEO_GENERATION_NODE = "video_generation"
VIDEO_CLONE_ANALYSIS_NODE = "video_clone_analysis"
VIDEO_CLONE_MAPPING_NODE = "video_clone_mapping"
VIDEO_CLONE_PROMPT_NODE = "video_clone_prompt"
VIDEO_CLONE_REVIEW_NODE = "video_clone_review"

APPROVAL_NODE_BY_AGENT_NODE = {
    DIRECTOR_NODE: DIRECTOR_APPROVAL_NODE,
    RESEARCH_NODE: RESEARCH_APPROVAL_NODE,
    PRODUCTION_NODE: PRODUCTION_APPROVAL_NODE,
    BRAND_PACKAGING_NODE: BRAND_PACKAGING_APPROVAL_NODE,
}
APPROVAL_NODE_NAMES = frozenset(APPROVAL_NODE_BY_AGENT_NODE.values())

WORKFLOW_NODE_NAMES = (
    INTENT_ROUTER_NODE,
    IMAGE_GENERATION_NODE,
    DIRECTOR_NODE,
    DIRECTOR_APPROVAL_NODE,
    RESEARCH_NODE,
    RESEARCH_APPROVAL_NODE,
    PRODUCTION_NODE,
    PRODUCTION_APPROVAL_NODE,
    BRAND_PACKAGING_NODE,
    BRAND_PACKAGING_APPROVAL_NODE,
    STRATEGY_NODE,
    STRATEGY_APPROVAL_NODE,
    COPYWRITING_NODE,
    COPYWRITING_APPROVAL_NODE,
    STORYBOARD_NODE,
    STORYBOARD_APPROVAL_NODE,
    VIDEO_PROMPT_NODE,
    VIDEO_PROMPT_APPROVAL_NODE,
    REVIEWER_NODE,
    REVIEWER_APPROVAL_NODE,
    VIDEO_GENERATION_NODE,
    VIDEO_CLONE_ANALYSIS_NODE,
    VIDEO_CLONE_MAPPING_NODE,
    VIDEO_CLONE_PROMPT_NODE,
    VIDEO_CLONE_REVIEW_NODE,
)

VideoStatusCallback = Callable[[VideoGenerationRequest, VideoTask], Awaitable[None]]


@dataclass(slots=True)
class IntentRouterNode:
    agent: IntentRouterAgent

    async def __call__(self, state: ContentWorkflowState) -> ContentWorkflowState:
        routing_input = IntentRoutingInput(
            request_text=state["request_text"],
            references=_references(state),
            requested_mode=RequestedMode(state.get("requested_mode", "full_creation")),
        )
        decision = await self.agent.execute(routing_input)
        values: ContentWorkflowState = {
            "intent_decision": decision.model_dump(mode="json"),
        }
        if decision.intent is TaskIntent.VIDEO_GENERATION:
            reference_ids = [
                reference.id
                for reference in routing_input.references
                if isinstance(
                    reference.snapshot.get("url") or reference.snapshot.get("source_url"),
                    str,
                )
            ]
            values["video_prompt"] = VideoPromptOutput(
                prompt=routing_input.request_text,
                duration_seconds=state.get("duration_seconds", 10),
                aspect_ratio=state.get("aspect_ratio", "9:16"),
                reference_ids=reference_ids[:10],
            ).model_dump(mode="json")
        return _node_update(
            state,
            node_name=INTENT_ROUTER_NODE,
            provider=self.agent.provider.provider_name,
            is_mock=self.agent.provider.is_mock,
            **values,
        )


class ImageGenerationUnavailableNode:
    async def __call__(self, state: ContentWorkflowState) -> ContentWorkflowState:
        del state
        raise CapabilityUnavailableError("image_generation")


def _references(state: ContentWorkflowState) -> list[ProjectReference]:
    return [ProjectReference.model_validate(reference) for reference in state.get("references", [])]


def _selected_strategy(state: ContentWorkflowState) -> StrategyOption:
    strategies = StrategyOutput.model_validate(state["strategies"])
    strategy_id = state.get("selected_strategy_id", strategies.recommended_strategy_id)
    selected = next(
        (option for option in strategies.strategy_options if option.strategy_id == strategy_id),
        None,
    )
    if selected is None:
        raise ValueError(f"Selected strategy does not exist: {strategy_id}")
    return selected


def _feedback(state: ContentWorkflowState, node_name: str) -> str | None:
    feedback = state.get("agent_feedback", {}).get(node_name)
    return feedback if isinstance(feedback, str) and feedback else None


def _next_attempts(state: ContentWorkflowState, node_name: str) -> dict[str, int]:
    attempts = dict(state.get("agent_attempts", {}))
    attempts[node_name] = attempts.get(node_name, 0) + 1
    return attempts


def _node_update(
    state: ContentWorkflowState,
    *,
    node_name: str,
    provider: str,
    is_mock: bool,
    provider_details: dict[str, Any] | None = None,
    **values: Any,
) -> ContentWorkflowState:
    provider_usage = dict(state.get("provider_usage", {}))
    provider_usage[node_name] = {
        "provider": provider,
        "is_mock": is_mock,
        **(provider_details or {}),
    }
    completed_nodes = [*state.get("completed_nodes", []), node_name]
    return {
        **values,
        "current_node": node_name,
        "completed_nodes": completed_nodes,
        "provider_usage": provider_usage,
        "agent_attempts": _next_attempts(state, node_name),
    }


@dataclass(slots=True)
class DirectorNode:
    agent: DirectorAgent

    async def __call__(self, state: ContentWorkflowState) -> ContentWorkflowState:
        agent_input = DirectorInput(
            request_text=state["request_text"],
            references=_references(state),
            blueprint=state.get("blueprint"),
            target_platform=state.get("target_platform", "douyin"),
            duration_seconds=state.get("duration_seconds", 20),
            aspect_ratio=state.get("aspect_ratio", "9:16"),
            requested_mode=RequestedMode(state.get("requested_mode", "full_creation")),
        )
        output = await self.agent.execute(
            agent_input,
            feedback=_feedback(state, DIRECTOR_NODE),
        )
        return _node_update(
            state,
            node_name=DIRECTOR_NODE,
            provider=self.agent.provider.provider_name,
            is_mock=self.agent.provider.is_mock,
            director=output.model_dump(mode="json"),
            creative_brief=output.creative_brief.model_dump(mode="json"),
        )


@dataclass(slots=True)
class ResearchNode:
    agent: ResearchStrategyAgent
    auto_select_recommended: bool = True

    async def __call__(self, state: ContentWorkflowState) -> ContentWorkflowState:
        agent_input = ResearchInput(
            request_text=state["request_text"],
            creative_brief=CreativeBrief.model_validate(state["creative_brief"]),
            references=_references(state),
        )
        output = await self.agent.execute(
            agent_input,
            feedback=_feedback(state, RESEARCH_NODE),
        )
        values: ContentWorkflowState = {
            "research_strategy": output.model_dump(mode="json"),
            "research": output.research.model_dump(mode="json"),
            "strategies": output.strategies.model_dump(mode="json"),
        }
        if self.auto_select_recommended:
            values["selected_strategy_id"] = output.strategies.recommended_strategy_id
        return _node_update(
            state,
            node_name=RESEARCH_NODE,
            provider=self.agent.model_provider.provider_name,
            is_mock=self.agent.model_provider.is_mock,
            provider_details={
                "research_provider": self.agent.research_provider.provider_name,
                "research_is_mock": self.agent.research_provider.is_mock,
            },
            **values,
        )


@dataclass(slots=True)
class ProductionNode:
    agent: ProductionAgent

    async def __call__(self, state: ContentWorkflowState) -> ContentWorkflowState:
        from .production import validate_production_package

        agent_input = ProductionInput(
            creative_brief=CreativeBrief.model_validate(state["creative_brief"]),
            selected_strategy=_selected_strategy(state),
            references=_references(state),
        )
        output = await self.agent.execute(
            agent_input,
            feedback=_feedback(state, PRODUCTION_NODE),
        )
        validate_production_package(output, agent_input)
        return _node_update(
            state,
            node_name=PRODUCTION_NODE,
            provider=self.agent.provider.provider_name,
            is_mock=self.agent.provider.is_mock,
            production=output.model_dump(mode="json"),
            production_plan=output.production_plan.model_dump(mode="json"),
            copywriting=output.copywriting.model_dump(mode="json"),
            storyboard=output.storyboard.model_dump(mode="json"),
            video_prompt=output.video_prompt.model_dump(mode="json"),
        )


@dataclass(slots=True)
class BrandPackagingNode:
    agent: BrandPackagingAgent

    async def __call__(self, state: ContentWorkflowState) -> ContentWorkflowState:
        agent_input = BrandPackagingInput(
            request_text=state["request_text"],
            creative_brief=CreativeBrief.model_validate(state["creative_brief"]),
            selected_strategy=_selected_strategy(state),
            references=_references(state),
        )
        output = await self.agent.execute(
            agent_input,
            feedback=_feedback(state, BRAND_PACKAGING_NODE),
        )
        reference_ids = {reference.id for reference in agent_input.references}
        unknown_ids = set(output.reference_ids) - reference_ids
        if unknown_ids:
            raise InvalidReferenceSubsetError(
                internal_agent=BRAND_PACKAGING_NODE,
                invalid_ids=sorted(unknown_ids),
                duplicate_ids=[],
                allowed_ids=sorted(reference_ids),
            )
        return _node_update(
            state,
            node_name=BRAND_PACKAGING_NODE,
            provider=self.agent.provider.provider_name,
            is_mock=self.agent.provider.is_mock,
            brand_packaging=output.model_dump(mode="json"),
        )


@dataclass(slots=True)
class StrategyNode:
    agent: StrategyAgent
    auto_select_recommended: bool = True

    async def __call__(self, state: ContentWorkflowState) -> ContentWorkflowState:
        agent_input = StrategyInput(
            creative_brief=CreativeBrief.model_validate(state["creative_brief"]),
            research=ResearchOutput.model_validate(state["research"]),
            references=_references(state),
        )
        output = await self.agent.execute(
            agent_input,
            feedback=_feedback(state, STRATEGY_NODE),
        )
        values: ContentWorkflowState = {
            "strategies": output.model_dump(mode="json"),
        }
        if self.auto_select_recommended:
            values["selected_strategy_id"] = output.recommended_strategy_id
        return _node_update(
            state,
            node_name=STRATEGY_NODE,
            provider=self.agent.provider.provider_name,
            is_mock=self.agent.provider.is_mock,
            **values,
        )


@dataclass(slots=True)
class AgentApprovalNode:
    node_name: str
    agent_name: str
    artifact_type: str | None = None
    require_strategy_id: bool = False

    async def __call__(self, state: ContentWorkflowState) -> ContentWorkflowState:
        strategy_ids: list[str] = []
        recommended_strategy_id: str | None = None
        if self.require_strategy_id:
            strategies = StrategyOutput.model_validate(state["strategies"])
            strategy_ids = [option.strategy_id for option in strategies.strategy_options]
            recommended_strategy_id = strategies.recommended_strategy_id
        decision = interrupt(
            {
                "type": "agent_approval",
                "node_name": self.node_name,
                "agent_name": self.agent_name,
                "attempt": state.get("agent_attempts", {}).get(self.node_name, 1),
                "artifact_type": self.artifact_type,
                "strategy_ids": strategy_ids,
                "recommended_strategy_id": recommended_strategy_id,
            }
        )
        if not isinstance(decision, dict):
            raise ValueError("Agent approval decision must be an object")

        # Compatibility with the original strategy-selection payload.
        action = decision.get("action")
        if self.require_strategy_id and action is None and decision.get("strategy_id"):
            action = "approve"
        if action not in {"approve", "retry"}:
            raise ValueError(f"Unsupported Agent approval action: {action}")
        decision_node = decision.get("node_name", self.node_name)
        if decision_node != self.node_name:
            raise ValueError(f"Decision targets {decision_node!r}, expected {self.node_name!r}")

        update: ContentWorkflowState = {
            "approval_action": action,
            "approval_node": self.node_name,
        }
        feedback = decision.get("feedback")
        if feedback is not None:
            if not isinstance(feedback, str) or not feedback.strip():
                raise ValueError("Agent retry feedback must be non-empty text")
            feedback_by_node = dict(state.get("agent_feedback", {}))
            feedback_by_node[self.node_name] = feedback.strip()
            update["agent_feedback"] = feedback_by_node

        if self.require_strategy_id:
            strategy_id = decision.get("strategy_id")
            if action == "approve":
                if strategy_id not in set(strategy_ids):
                    raise ValueError(f"Selected strategy does not exist: {strategy_id}")
                update["selected_strategy_id"] = strategy_id
            else:
                update["selected_strategy_id"] = None
        return update


class StrategyApprovalNode(AgentApprovalNode):
    """Compatibility name for the Strategy Agent approval gate."""

    def __init__(self) -> None:
        super().__init__(
            node_name=STRATEGY_NODE,
            agent_name="strategy",
            artifact_type="strategy",
            require_strategy_id=True,
        )


class ResearchStrategyApprovalNode(AgentApprovalNode):
    def __init__(self) -> None:
        super().__init__(
            node_name=RESEARCH_NODE,
            agent_name="research",
            artifact_type="strategy",
            require_strategy_id=True,
        )


@dataclass(slots=True)
class ReviewerNode:
    agent: ReviewerAgent

    async def __call__(self, state: ContentWorkflowState) -> ContentWorkflowState:
        agent_input = ReviewerInput(
            creative_brief=CreativeBrief.model_validate(state["creative_brief"]),
            selected_strategy=_selected_strategy(state),
            copywriting=CopywritingOutput.model_validate(state["copywriting"]),
            storyboard=StoryboardOutput.model_validate(state["storyboard"]),
            video_prompt=VideoPromptOutput.model_validate(state["video_prompt"]),
            references=_references(state),
        )
        output = await self.agent.execute(
            agent_input,
            feedback=_feedback(state, REVIEWER_NODE),
        )
        return _node_update(
            state,
            node_name=REVIEWER_NODE,
            provider=self.agent.provider.provider_name,
            is_mock=self.agent.provider.is_mock,
            review=output.model_dump(mode="json"),
        )


@dataclass(slots=True)
class VideoGenerationNode:
    provider: VideoProvider
    max_status_polls: int = 20
    status_callback: VideoStatusCallback | None = None
    reference_resolver: VideoReferenceResolver | None = None

    async def __call__(self, state: ContentWorkflowState) -> ContentWorkflowState:
        video_prompt = VideoPromptOutput.model_validate(state["video_prompt"])
        selected_ids = set(video_prompt.reference_ids)
        allowed_ids = [
            reference.get("id")
            for reference in state.get("references", [])
            if isinstance(reference.get("id"), str)
        ]
        invalid_ids = list(
            dict.fromkeys(
                item for item in video_prompt.reference_ids if item not in set(allowed_ids)
            )
        )
        if invalid_ids:
            raise InvalidReferenceSubsetError(
                internal_agent="video_prompt_agent",
                invalid_ids=invalid_ids,
                duplicate_ids=[],
                allowed_ids=allowed_ids,
            )
        reference_urls: list[str] = []
        for reference in state.get("references", []):
            if reference.get("id") not in selected_ids:
                continue
            reference_id = reference.get("id")
            if self.reference_resolver is not None and isinstance(reference_id, str):
                resolved_url = await self.reference_resolver(reference_id)
                if resolved_url is not None:
                    reference_urls.append(resolved_url)
                    continue
            snapshot = reference.get("snapshot", {})
            if not isinstance(snapshot, dict):
                continue
            url = snapshot.get("url") or snapshot.get("source_url")
            if isinstance(url, str) and url:
                reference_urls.append(url)
        request = VideoGenerationRequest(
            project_id=state["project_id"],
            prompt=video_prompt.prompt,
            negative_prompt=video_prompt.negative_prompt,
            duration_seconds=video_prompt.duration_seconds,
            aspect_ratio=video_prompt.aspect_ratio,
            reference_urls=reference_urls[:10],
            provider_parameters=video_prompt.provider_parameters,
        )
        task = await self.provider.submit(request=request)
        await self._publish_status(request, task)
        history = [task.model_dump(mode="json")]
        for _ in range(self.max_status_polls):
            if task.status in {
                VideoTaskStatus.COMPLETED,
                VideoTaskStatus.FAILED,
                VideoTaskStatus.CANCELLED,
            }:
                break
            task = await self.provider.get_status(task_id=task.task_id)
            await self._publish_status(request, task)
            history.append(task.model_dump(mode="json"))
        else:
            raise TimeoutError(
                f"Video task {task.task_id} did not reach a terminal state after "
                f"{self.max_status_polls} polls"
            )
        return _node_update(
            state,
            node_name=VIDEO_GENERATION_NODE,
            provider=self.provider.provider_name,
            is_mock=self.provider.is_mock,
            video_task=task.model_dump(mode="json"),
            video_task_history=history,
        )

    async def _publish_status(
        self,
        request: VideoGenerationRequest,
        task: VideoTask,
    ) -> None:
        if self.status_callback is not None:
            await self.status_callback(request, task)


def _video_clone_references(
    state: ContentWorkflowState,
) -> tuple[ProjectReference, list[ProjectReference]]:
    references = _references(state)
    source = [reference for reference in references if reference.type.value == "reference_video"]
    if len(source) != 1:
        raise ValueError("视频复刻必须且只能提供一个参考视频")
    replacements = [reference for reference in references if reference.id != source[0].id]
    if not replacements:
        raise ValueError("视频复刻至少需要一个替换素材")
    return source[0], replacements


async def _resolved_reference_images(
    references: list[ProjectReference],
    resolver: VideoReferenceResolver | None,
) -> list[tuple[str, str]]:
    resolved: list[tuple[str, str]] = []
    for reference in references:
        url = await resolver(reference.id) if resolver is not None else None
        if url is None:
            snapshot_url = reference.snapshot.get("url") or reference.snapshot.get(
                "source_url"
            )
            url = snapshot_url if isinstance(snapshot_url, str) else None
        if url:
            resolved.append((reference.id, url))
    return resolved


@dataclass(slots=True)
class VideoCloneAnalysisNode:
    provider: VideoUnderstandingProvider

    async def __call__(self, state: ContentWorkflowState) -> ContentWorkflowState:
        reference, _ = _video_clone_references(state)
        output = await self.provider.analyze(
            request=VideoCloneAnalysisRequest(
                project_id=state["project_id"],
                request_text=state["request_text"],
                reference=reference,
                target_platform=state.get("target_platform", "douyin"),
                duration_seconds=state.get("duration_seconds", 10),
                aspect_ratio=state.get("aspect_ratio", "9:16"),
            )
        )
        return _node_update(
            state,
            node_name=VIDEO_CLONE_ANALYSIS_NODE,
            provider=self.provider.provider_name,
            is_mock=self.provider.is_mock,
            video_clone_analysis=output.model_dump(mode="json"),
        )


@dataclass(slots=True)
class VideoCloneMappingNode:
    agent: VideoCloneMappingAgent
    reference_resolver: VideoReferenceResolver | None = None

    async def __call__(self, state: ContentWorkflowState) -> ContentWorkflowState:
        _, replacements = _video_clone_references(state)
        analysis = VideoCloneAnalysisOutput.model_validate(state["video_clone_analysis"])
        output = await self.agent.execute(
            VideoCloneMappingInput(
                request_text=state["request_text"],
                analysis=analysis,
                replacement_references=replacements,
                target_platform=state.get("target_platform", "douyin"),
            ),
            reference_images=await _resolved_reference_images(
                replacements,
                self.reference_resolver,
            ),
        )
        allowed_ids = {reference.id for reference in replacements}
        used_ids = set(output.replacement_reference_ids)
        for item in output.mappings:
            used_ids.update(item.replacement_reference_ids)
        invalid_ids = sorted(used_ids - allowed_ids)
        if invalid_ids:
            raise InvalidReferenceSubsetError(
                internal_agent=VIDEO_CLONE_MAPPING_NODE,
                invalid_ids=invalid_ids,
                duplicate_ids=[],
                allowed_ids=sorted(allowed_ids),
            )
        expected_shots = {shot.shot_id for shot in analysis.shots}
        mapped_shots = {item.shot_id for item in output.mappings}
        if mapped_shots != expected_shots:
            raise ValueError("视频复刻素材映射必须完整覆盖解析出的镜头")
        return _node_update(
            state,
            node_name=VIDEO_CLONE_MAPPING_NODE,
            provider=self.agent.provider.provider_name,
            is_mock=self.agent.provider.is_mock,
            video_clone_mapping=output.model_dump(mode="json"),
        )


@dataclass(slots=True)
class VideoClonePromptNode:
    agent: VideoClonePromptAgent
    reference_resolver: VideoReferenceResolver | None = None

    async def __call__(self, state: ContentWorkflowState) -> ContentWorkflowState:
        references = _references(state)
        mapping = VideoCloneMappingOutput.model_validate(state["video_clone_mapping"])
        _, replacements = _video_clone_references(state)
        output = await self.agent.execute(
            VideoClonePromptInput(
                request_text=state["request_text"],
                analysis=VideoCloneAnalysisOutput.model_validate(
                    state["video_clone_analysis"]
                ),
                mapping=mapping,
                references=references,
                duration_seconds=state.get("duration_seconds", 10),
                aspect_ratio=state.get("aspect_ratio", "9:16"),
            ),
            reference_images=await _resolved_reference_images(
                replacements,
                self.reference_resolver,
            ),
        )
        allowed_ids = {reference.id for reference in references}
        used_ids = set(output.generation.reference_ids)
        for shot in output.shot_prompts:
            used_ids.update(shot.reference_ids)
        invalid_ids = sorted(used_ids - allowed_ids)
        if invalid_ids:
            raise InvalidReferenceSubsetError(
                internal_agent=VIDEO_CLONE_PROMPT_NODE,
                invalid_ids=invalid_ids,
                duplicate_ids=[],
                allowed_ids=sorted(allowed_ids),
            )
        if output.generation.duration_seconds != state.get("duration_seconds", 10):
            raise ValueError("视频复刻生成提示词的时长必须等于用户配置")
        if output.generation.aspect_ratio != state.get("aspect_ratio", "9:16"):
            raise ValueError("视频复刻生成提示词的画幅必须等于用户配置")
        if {shot.shot_id for shot in output.shot_prompts} != {
            item.shot_id for item in mapping.mappings
        }:
            raise ValueError("视频复刻逐镜头提示词必须完整覆盖素材映射")
        return _node_update(
            state,
            node_name=VIDEO_CLONE_PROMPT_NODE,
            provider=self.agent.provider.provider_name,
            is_mock=self.agent.provider.is_mock,
            video_clone_prompt=output.model_dump(mode="json"),
            video_prompt=output.generation.model_dump(mode="json"),
        )


@dataclass(slots=True)
class VideoCloneReviewNode:
    provider: VideoUnderstandingProvider

    async def __call__(self, state: ContentWorkflowState) -> ContentWorkflowState:
        task = VideoTask.model_validate(state["video_task"])
        if task.status is not VideoTaskStatus.COMPLETED or not task.result_url:
            raise ValueError("生成视频未完成，无法执行复刻验收")
        _, replacements = _video_clone_references(state)
        output = await self.provider.review(
            request=VideoCloneReviewRequest(
                project_id=state["project_id"],
                result_url=task.result_url,
                analysis=VideoCloneAnalysisOutput.model_validate(
                    state["video_clone_analysis"]
                ),
                mapping=VideoCloneMappingOutput.model_validate(state["video_clone_mapping"]),
                prompt=VideoClonePromptOutput.model_validate(state["video_clone_prompt"]),
                replacement_references=replacements,
            )
        )
        return _node_update(
            state,
            node_name=VIDEO_CLONE_REVIEW_NODE,
            provider=self.provider.provider_name,
            is_mock=self.provider.is_mock,
            video_clone_review=output.model_dump(mode="json"),
        )
