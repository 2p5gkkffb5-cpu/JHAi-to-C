from pathlib import Path

import pytest
from pydantic import ValidationError

from jhai_to_c.agents import (
    AgentConfig,
    AgentName,
    AgentRegistry,
    DuplicateAgentError,
    UnknownAgentError,
    build_default_agent_registry,
)
from jhai_to_c.prompts import (
    EmptyPromptError,
    InvalidPromptNameError,
    PromptLoader,
    PromptNotFoundError,
)


def test_agent_config_is_strict_and_immutable() -> None:
    config = AgentConfig(
        name=AgentName.RESEARCH,
        role="Research role",
        prompt_names=("research",),
    )

    with pytest.raises(ValidationError):
        config.role = "Changed role"

    with pytest.raises(ValidationError):
        AgentConfig(
            name=AgentName.RESEARCH,
            role="Research role",
            prompt_names=("research",),
            model="another-model",
        )


def test_agent_config_rejects_duplicate_prompt_names() -> None:
    with pytest.raises(ValidationError, match="prompt_names must be unique"):
        AgentConfig(
            name=AgentName.PRODUCTION,
            role="Production role",
            prompt_names=("production_copywriting", "production_copywriting"),
        )


def test_agent_config_rejects_unsafe_prompt_names() -> None:
    with pytest.raises(ValidationError, match="invalid prompt name"):
        AgentConfig(
            name=AgentName.RESEARCH,
            role="Research role",
            prompt_names=("../research",),
        )


def test_default_registry_contains_target_topology() -> None:
    registry = build_default_agent_registry()

    assert registry.names == (
        AgentName.SUPERVISOR,
        AgentName.RESEARCH,
        AgentName.PRODUCTION,
    )
    with pytest.raises(UnknownAgentError):
        registry.get("strategy")


def test_registry_rejects_duplicate_and_unknown_agents() -> None:
    config = AgentConfig(
        name=AgentName.REVIEWER,
        role="Reviewer role",
        prompt_names=("reviewer",),
    )
    registry = AgentRegistry((config,))

    with pytest.raises(DuplicateAgentError, match="reviewer"):
        registry.register(config)
    with pytest.raises(UnknownAgentError):
        registry.get("supervisor")
    with pytest.raises(UnknownAgentError):
        registry.get("not-an-agent")


def test_default_prompt_loader_resolves_every_registered_prompt() -> None:
    registry = build_default_agent_registry()
    loader = PromptLoader()

    prompts = loader.load_many(
        prompt_name for config in registry for prompt_name in config.prompt_names
    )

    assert set(prompts) == {
        "supervisor",
        "research_strategy",
        "production",
    }
    assert all(prompt.strip() == prompt for prompt in prompts.values())


def test_prompt_loader_rejects_unsafe_missing_and_empty_resources(tmp_path: Path) -> None:
    loader = PromptLoader(tmp_path)

    with pytest.raises(InvalidPromptNameError):
        loader.load("../secret")
    with pytest.raises(PromptNotFoundError):
        loader.load("missing")

    (tmp_path / "empty.md").write_text("  \n", encoding="utf-8")
    with pytest.raises(EmptyPromptError):
        loader.load("empty")


def test_video_clone_prompt_encodes_director_timeline_and_generation_defaults() -> None:
    prompt = PromptLoader().load("video_clone_prompt")

    assert "0–2 秒钩子" in prompt
    assert "13–15 秒收束定格" in prompt
    assert "禁止把 UUID" in prompt
    assert 'resolution="1080p"' in prompt
    assert "不包含用于结构分析的" in prompt
    assert "素材图片自带背景" in prompt
    assert "区分发光实体、环境光、投影和反射" in prompt
