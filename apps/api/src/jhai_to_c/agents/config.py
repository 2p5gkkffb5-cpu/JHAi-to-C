from enum import StrEnum

from pydantic import ConfigDict, Field, field_validator

from jhai_to_c.contracts.common import ContractModel
from jhai_to_c.prompts.loader import validate_prompt_name


class AgentName(StrEnum):
    """Stable internal identities for the target multi-agent topology."""

    SUPERVISOR = "supervisor"
    RESEARCH = "research"
    STRATEGY = "strategy"
    # Legacy persistence identity. It is intentionally absent from the active registry.
    PRODUCTION = "production"
    PRODUCTION_COORDINATOR = "production_coordinator"
    COPYWRITER_AGENT = "copywriter_agent"
    STORYBOARD_AGENT = "storyboard_agent"
    VIDEO_PROMPT_AGENT = "video_prompt_agent"
    REVIEWER = "reviewer"


class AgentConfig(ContractModel):
    """Declarative agent metadata without runtime providers or workflow state."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        frozen=True,
    )

    name: AgentName
    role: str = Field(min_length=1, max_length=500)
    prompt_names: tuple[str, ...] = Field(min_length=1, max_length=10)

    @field_validator("prompt_names")
    @classmethod
    def validate_prompt_names(cls, prompt_names: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(prompt_names)) != len(prompt_names):
            raise ValueError("prompt_names must be unique")
        for prompt_name in prompt_names:
            validate_prompt_name(prompt_name)
        return prompt_names


DEFAULT_AGENT_CONFIGS: tuple[AgentConfig, ...] = (
    AgentConfig(
        name=AgentName.SUPERVISOR,
        role="整理创意简报并监督受限的工作流路由。",
        prompt_names=("supervisor",),
    ),
    AgentConfig(
        name=AgentName.RESEARCH,
        role="检索可追溯资料，并一次生成研究结论与三套内容策略。",
        prompt_names=("research_strategy",),
    ),
    AgentConfig(
        name=AgentName.PRODUCTION,
        role="一次生成制作计划、营销文案、分镜和最终视频提示词。",
        prompt_names=("production",),
    ),
)


# Compatibility-only configs for the retired eight-Agent topology. They are not
# registered by default and therefore cannot add LLM calls to the active graph.
LEGACY_AGENT_CONFIGS: dict[AgentName, AgentConfig] = {
    AgentName.REVIEWER: AgentConfig(
        name=AgentName.REVIEWER,
        role="审核内容产物的一致性、合规性与可生成性。",
        prompt_names=("reviewer",),
    ),
    AgentName.STRATEGY: AgentConfig(
        name=AgentName.STRATEGY,
        role="基于创意简报和研究证据制定内容策略。",
        prompt_names=("strategy",),
    ),
    AgentName.PRODUCTION_COORDINATOR: AgentConfig(
        name=AgentName.PRODUCTION_COORDINATOR,
        role="生成生产执行约束并协调三个专业 Agent。",
        prompt_names=("production_coordinator",),
    ),
    AgentName.COPYWRITER_AGENT: AgentConfig(
        name=AgentName.COPYWRITER_AGENT,
        role="生成短视频标题、钩子、旁白、屏幕文字和 CTA。",
        prompt_names=("production_copywriting",),
    ),
    AgentName.STORYBOARD_AGENT: AgentConfig(
        name=AgentName.STORYBOARD_AGENT,
        role="将已确认文案拆成连续、可执行的分镜。",
        prompt_names=("production_storyboard",),
    ),
    AgentName.VIDEO_PROMPT_AGENT: AgentConfig(
        name=AgentName.VIDEO_PROMPT_AGENT,
        role="将文案与分镜转换为视频 Provider 可消费的最终提示词。",
        prompt_names=("production_video_prompt",),
    ),
}
