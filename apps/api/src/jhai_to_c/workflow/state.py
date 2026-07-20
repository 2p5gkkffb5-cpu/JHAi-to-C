from typing import Any, Literal, TypedDict


class StateError(TypedDict):
    code: str
    message: str
    node: str | None
    details: dict[str, Any]


class StateVideoTask(TypedDict, total=False):
    task_id: str
    provider: str
    is_mock: bool
    status: Literal["queued", "processing", "completed", "failed", "cancelled"]
    progress: float | None
    result_url: str | None
    error_code: str | None
    error_message: str | None


class ContentWorkflowState(TypedDict, total=False):
    """JSON-serializable state boundary for the Phase 1 LangGraph StateGraph."""

    project_id: str
    request_text: str
    references: list[dict[str, Any]]
    blueprint: dict[str, Any] | None
    target_platform: str
    duration_seconds: int
    aspect_ratio: Literal["9:16", "16:9", "1:1"]
    requested_mode: Literal[
        "auto",
        "full_creation",
        "video_generation",
        "image_generation",
        "brand_packaging",
        "video_clone",
    ]
    intent_decision: dict[str, Any]

    director: dict[str, Any]
    creative_brief: dict[str, Any]
    research: dict[str, Any]
    research_strategy: dict[str, Any]
    strategies: dict[str, Any]
    selected_strategy_id: str
    production_plan: dict[str, Any]
    production: dict[str, Any]
    brand_packaging: dict[str, Any]
    copywriting: dict[str, Any]
    storyboard: dict[str, Any]
    video_prompt: dict[str, Any]
    review: dict[str, Any]
    video_task: StateVideoTask
    video_task_history: list[StateVideoTask]
    video_clone_analysis: dict[str, Any]
    video_clone_mapping: dict[str, Any]
    video_clone_prompt: dict[str, Any]
    video_clone_review: dict[str, Any]

    current_node: str
    completed_nodes: list[str]
    provider_usage: dict[str, dict[str, Any]]
    agent_feedback: dict[str, str]
    agent_attempts: dict[str, int]
    approval_action: Literal["approve", "retry"]
    approval_node: str
    retry_count: int
    errors: list[StateError]
