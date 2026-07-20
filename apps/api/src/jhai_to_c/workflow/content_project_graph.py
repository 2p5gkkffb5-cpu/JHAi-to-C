from typing import Any

from langgraph.graph import END, START, StateGraph

from jhai_to_c.agents import (
    AgentName,
    AgentRegistry,
    build_default_agent_registry,
)
from jhai_to_c.agents.director import DirectorAgent
from jhai_to_c.agents.intent import IntentRouterAgent
from jhai_to_c.agents.packaging import BrandPackagingAgent
from jhai_to_c.agents.production import ProductionAgent
from jhai_to_c.agents.research import ResearchStrategyAgent
from jhai_to_c.agents.video_clone import VideoCloneMappingAgent, VideoClonePromptAgent
from jhai_to_c.prompts import PromptLoader
from jhai_to_c.prompts.loader import PromptNotFoundError
from jhai_to_c.providers.interfaces import (
    AgentModelProvider,
    ResearchProvider,
    VideoProvider,
    VideoUnderstandingProvider,
)
from jhai_to_c.providers.mock import (
    DeterministicMockAgentModelProvider,
    DeterministicMockResearchProvider,
    DeterministicMockVideoProvider,
    DeterministicMockVideoUnderstandingProvider,
)

from .nodes import (
    BRAND_PACKAGING_APPROVAL_NODE,
    BRAND_PACKAGING_NODE,
    DIRECTOR_APPROVAL_NODE,
    DIRECTOR_NODE,
    IMAGE_GENERATION_NODE,
    INTENT_ROUTER_NODE,
    PRODUCTION_APPROVAL_NODE,
    PRODUCTION_NODE,
    RESEARCH_APPROVAL_NODE,
    RESEARCH_NODE,
    VIDEO_CLONE_ANALYSIS_NODE,
    VIDEO_CLONE_MAPPING_NODE,
    VIDEO_CLONE_PROMPT_NODE,
    VIDEO_CLONE_REVIEW_NODE,
    VIDEO_GENERATION_NODE,
    AgentApprovalNode,
    BrandPackagingNode,
    DirectorNode,
    ImageGenerationUnavailableNode,
    IntentRouterNode,
    ProductionNode,
    ResearchNode,
    ResearchStrategyApprovalNode,
    VideoCloneAnalysisNode,
    VideoCloneMappingNode,
    VideoClonePromptNode,
    VideoCloneReviewNode,
    VideoGenerationNode,
    VideoReferenceResolver,
    VideoStatusCallback,
)
from .state import ContentWorkflowState


def _route_approval(state: ContentWorkflowState) -> str:
    action = state.get("approval_action")
    if action not in {"approve", "retry"}:
        raise ValueError(f"Unknown Agent approval action: {action}")
    return action


def _route_intent(state: ContentWorkflowState) -> str:
    decision = state.get("intent_decision", {})
    intent = decision.get("intent") if isinstance(decision, dict) else None
    if intent not in {
        "full_creation",
        "video_generation",
        "image_generation",
        "brand_packaging",
        "video_clone",
    }:
        raise ValueError(f"Unknown routed intent: {intent}")
    return intent


def _route_after_research(state: ContentWorkflowState) -> str:
    decision = state.get("intent_decision", {})
    intent = decision.get("intent") if isinstance(decision, dict) else "full_creation"
    return BRAND_PACKAGING_NODE if intent == "brand_packaging" else PRODUCTION_NODE


def _route_after_research_approval(state: ContentWorkflowState) -> str:
    if state.get("approval_action") == "retry":
        return "retry"
    return _route_after_research(state)


def _route_after_video_generation(state: ContentWorkflowState) -> str:
    decision = state.get("intent_decision", {})
    intent = decision.get("intent") if isinstance(decision, dict) else None
    return VIDEO_CLONE_REVIEW_NODE if intent == "video_clone" else "end"


def build_content_project_graph(
    *,
    agent_model_provider: AgentModelProvider | None = None,
    research_provider: ResearchProvider | None = None,
    video_provider: VideoProvider | None = None,
    video_understanding_provider: VideoUnderstandingProvider | None = None,
    video_max_status_polls: int = 20,
    video_status_callback: VideoStatusCallback | None = None,
    video_reference_resolver: VideoReferenceResolver | None = None,
    agent_registry: AgentRegistry | None = None,
    prompt_loader: PromptLoader | None = None,
    checkpointer: Any = None,
    require_strategy_confirmation: bool = False,
    require_agent_approval: bool = False,
    require_final_approval: bool = False,
    enable_intent_routing: bool = False,
):
    """Build the compatible graph with registry-configured professional Agents."""

    model = (
        agent_model_provider
        if agent_model_provider is not None
        else DeterministicMockAgentModelProvider()
    )
    research = (
        research_provider if research_provider is not None else DeterministicMockResearchProvider()
    )
    video = video_provider if video_provider is not None else DeterministicMockVideoProvider()
    video_understanding = (
        video_understanding_provider
        if video_understanding_provider is not None
        else DeterministicMockVideoUnderstandingProvider()
    )
    registry = agent_registry if agent_registry is not None else build_default_agent_registry()
    loader = prompt_loader if prompt_loader is not None else PromptLoader()

    supervisor_config = registry.get(AgentName.SUPERVISOR)
    research_config = registry.get(AgentName.RESEARCH)
    production_config = registry.get(AgentName.PRODUCTION)

    supervisor_agent = DirectorAgent(
        model,
        config=supervisor_config,
        system_prompt=loader.load(supervisor_config.prompt_names[0]),
    )
    research_agent = ResearchStrategyAgent(
        model,
        research,
        config=research_config,
        system_prompt=loader.load(research_config.prompt_names[0]),
    )
    production_agent = ProductionAgent(
        model,
        config=production_config,
        system_prompt=loader.load(production_config.prompt_names[0]),
    )
    try:
        packaging_prompt = loader.load("brand_packaging")
    except PromptNotFoundError:
        packaging_prompt = PromptLoader().load("brand_packaging")
    packaging_agent = BrandPackagingAgent(model, system_prompt=packaging_prompt)
    try:
        video_clone_mapping_prompt = loader.load("video_clone_mapping")
        video_clone_prompt = loader.load("video_clone_prompt")
    except PromptNotFoundError:
        default_loader = PromptLoader()
        video_clone_mapping_prompt = default_loader.load("video_clone_mapping")
        video_clone_prompt = default_loader.load("video_clone_prompt")
    video_clone_mapping_agent = VideoCloneMappingAgent(
        model,
        system_prompt=video_clone_mapping_prompt,
    )
    video_clone_prompt_agent = VideoClonePromptAgent(
        model,
        system_prompt=video_clone_prompt,
    )
    graph = StateGraph(ContentWorkflowState)
    if enable_intent_routing:
        intent_router_agent = IntentRouterAgent(
            model,
            system_prompt=loader.load("intent_router"),
        )
        graph.add_node(INTENT_ROUTER_NODE, IntentRouterNode(intent_router_agent))
        graph.add_node(IMAGE_GENERATION_NODE, ImageGenerationUnavailableNode())
    graph.add_node(DIRECTOR_NODE, DirectorNode(supervisor_agent))
    graph.add_node(
        RESEARCH_NODE,
        ResearchNode(
            research_agent,
            auto_select_recommended=not (require_strategy_confirmation or require_agent_approval),
        ),
    )
    if require_strategy_confirmation or require_agent_approval:
        graph.add_node(RESEARCH_APPROVAL_NODE, ResearchStrategyApprovalNode())
    graph.add_node(PRODUCTION_NODE, ProductionNode(production_agent))
    graph.add_node(BRAND_PACKAGING_NODE, BrandPackagingNode(packaging_agent))
    graph.add_node(
        VIDEO_GENERATION_NODE,
        VideoGenerationNode(
            video,
            max_status_polls=video_max_status_polls,
            status_callback=video_status_callback,
            reference_resolver=video_reference_resolver,
        ),
    )
    graph.add_node(
        VIDEO_CLONE_ANALYSIS_NODE,
        VideoCloneAnalysisNode(video_understanding),
    )
    graph.add_node(
        VIDEO_CLONE_MAPPING_NODE,
        VideoCloneMappingNode(
            video_clone_mapping_agent,
            reference_resolver=video_reference_resolver,
        ),
    )
    graph.add_node(
        VIDEO_CLONE_PROMPT_NODE,
        VideoClonePromptNode(
            video_clone_prompt_agent,
            reference_resolver=video_reference_resolver,
        ),
    )
    graph.add_node(
        VIDEO_CLONE_REVIEW_NODE,
        VideoCloneReviewNode(video_understanding),
    )
    if require_agent_approval or require_final_approval:
        graph.add_node(
            PRODUCTION_APPROVAL_NODE,
            AgentApprovalNode(
                node_name=PRODUCTION_NODE,
                agent_name="production",
                artifact_type="production",
            ),
        )
        graph.add_node(
            BRAND_PACKAGING_APPROVAL_NODE,
            AgentApprovalNode(
                node_name=BRAND_PACKAGING_NODE,
                agent_name="brand_packaging",
                artifact_type="brand_packaging",
            ),
        )

    if enable_intent_routing:
        graph.add_edge(START, INTENT_ROUTER_NODE)
        graph.add_conditional_edges(
            INTENT_ROUTER_NODE,
            _route_intent,
            {
                "full_creation": DIRECTOR_NODE,
                "video_generation": VIDEO_GENERATION_NODE,
                "image_generation": IMAGE_GENERATION_NODE,
                "brand_packaging": DIRECTOR_NODE,
                "video_clone": VIDEO_CLONE_ANALYSIS_NODE,
            },
        )
        graph.add_edge(IMAGE_GENERATION_NODE, END)
    else:
        graph.add_edge(START, DIRECTOR_NODE)
    if require_agent_approval:
        graph.add_node(
            DIRECTOR_APPROVAL_NODE,
            AgentApprovalNode(
                node_name=DIRECTOR_NODE,
                agent_name="director",
                artifact_type="creative_brief",
            ),
        )
        graph.add_edge(DIRECTOR_NODE, DIRECTOR_APPROVAL_NODE)
        graph.add_conditional_edges(
            DIRECTOR_APPROVAL_NODE,
            _route_approval,
            {"approve": RESEARCH_NODE, "retry": DIRECTOR_NODE},
        )
        graph.add_edge(RESEARCH_NODE, RESEARCH_APPROVAL_NODE)
        graph.add_conditional_edges(
            RESEARCH_APPROVAL_NODE,
            _route_after_research_approval,
            {
                "production": PRODUCTION_NODE,
                "brand_packaging": BRAND_PACKAGING_NODE,
                "retry": RESEARCH_NODE,
            },
        )
        graph.add_edge(PRODUCTION_NODE, PRODUCTION_APPROVAL_NODE)
        graph.add_conditional_edges(
            PRODUCTION_APPROVAL_NODE,
            _route_approval,
            {"approve": VIDEO_GENERATION_NODE, "retry": PRODUCTION_NODE},
        )
        graph.add_edge(BRAND_PACKAGING_NODE, BRAND_PACKAGING_APPROVAL_NODE)
        graph.add_conditional_edges(
            BRAND_PACKAGING_APPROVAL_NODE,
            _route_approval,
            {"approve": END, "retry": BRAND_PACKAGING_NODE},
        )
    else:
        graph.add_edge(DIRECTOR_NODE, RESEARCH_NODE)
    if require_strategy_confirmation and not require_agent_approval:
        graph.add_edge(RESEARCH_NODE, RESEARCH_APPROVAL_NODE)
        graph.add_conditional_edges(
            RESEARCH_APPROVAL_NODE,
            _route_after_research,
            {"production": PRODUCTION_NODE, "brand_packaging": BRAND_PACKAGING_NODE},
        )
    elif not require_agent_approval:
        graph.add_conditional_edges(
            RESEARCH_NODE,
            _route_after_research,
            {"production": PRODUCTION_NODE, "brand_packaging": BRAND_PACKAGING_NODE},
        )
    if require_final_approval and not require_agent_approval:
        graph.add_edge(PRODUCTION_NODE, PRODUCTION_APPROVAL_NODE)
        graph.add_conditional_edges(
            PRODUCTION_APPROVAL_NODE,
            _route_approval,
            {"approve": VIDEO_GENERATION_NODE, "retry": PRODUCTION_NODE},
        )
    elif not require_agent_approval:
        graph.add_edge(PRODUCTION_NODE, VIDEO_GENERATION_NODE)
    if require_final_approval and not require_agent_approval:
        graph.add_edge(BRAND_PACKAGING_NODE, BRAND_PACKAGING_APPROVAL_NODE)
        graph.add_conditional_edges(
            BRAND_PACKAGING_APPROVAL_NODE,
            _route_approval,
            {"approve": END, "retry": BRAND_PACKAGING_NODE},
        )
    elif not require_agent_approval:
        graph.add_edge(BRAND_PACKAGING_NODE, END)
    graph.add_edge(VIDEO_CLONE_ANALYSIS_NODE, VIDEO_CLONE_MAPPING_NODE)
    graph.add_edge(VIDEO_CLONE_MAPPING_NODE, VIDEO_CLONE_PROMPT_NODE)
    graph.add_edge(VIDEO_CLONE_PROMPT_NODE, VIDEO_GENERATION_NODE)
    graph.add_conditional_edges(
        VIDEO_GENERATION_NODE,
        _route_after_video_generation,
        {VIDEO_CLONE_REVIEW_NODE: VIDEO_CLONE_REVIEW_NODE, "end": END},
    )
    graph.add_edge(VIDEO_CLONE_REVIEW_NODE, END)

    return graph.compile(checkpointer=checkpointer, name="content_project_graph")


content_project_graph = build_content_project_graph
