"""Phase 1 agents with independent prompts and structured contracts."""

from .config import DEFAULT_AGENT_CONFIGS, AgentConfig, AgentName
from .director import DirectorAgent, DirectorInput
from .intent import IntentRouterAgent
from .production import (
    CopywriterAgent,
    CopywriterInput,
    CopywritingInput,
    ProductionAgent,
    ProductionCoordinatorAgent,
    ProductionCoordinatorInput,
    ProductionInput,
    StoryboardAgent,
    StoryboardAgentInput,
    StoryboardInput,
    VideoPromptAgent,
    VideoPromptAgentInput,
    VideoPromptInput,
)
from .registry import (
    AgentRegistry,
    DuplicateAgentError,
    UnknownAgentError,
    build_default_agent_registry,
)
from .research import ResearchAgent, ResearchInput, ResearchStrategyAgent
from .reviewer import ReviewerAgent, ReviewerInput
from .strategy import StrategyAgent, StrategyInput
from .video_clone import (
    VideoCloneMappingAgent,
    VideoCloneMappingInput,
    VideoClonePromptAgent,
    VideoClonePromptInput,
)

__all__ = [
    "AgentConfig",
    "AgentName",
    "AgentRegistry",
    "CopywritingInput",
    "CopywriterAgent",
    "CopywriterInput",
    "DEFAULT_AGENT_CONFIGS",
    "DirectorAgent",
    "DirectorInput",
    "DuplicateAgentError",
    "IntentRouterAgent",
    "ProductionCoordinatorAgent",
    "ProductionCoordinatorInput",
    "ProductionAgent",
    "ProductionInput",
    "ResearchAgent",
    "ResearchInput",
    "ResearchStrategyAgent",
    "ReviewerAgent",
    "ReviewerInput",
    "StoryboardInput",
    "StoryboardAgent",
    "StoryboardAgentInput",
    "StrategyAgent",
    "StrategyInput",
    "UnknownAgentError",
    "VideoPromptInput",
    "VideoPromptAgent",
    "VideoPromptAgentInput",
    "build_default_agent_registry",
    "VideoCloneMappingAgent",
    "VideoCloneMappingInput",
    "VideoClonePromptAgent",
    "VideoClonePromptInput",
]
