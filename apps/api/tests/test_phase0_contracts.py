from typing import get_type_hints

import pytest
from pydantic import ValidationError

from jhai_to_c.config import Settings
from jhai_to_c.contracts import (
    ContentProjectCreate,
    ContentProjectRead,
    CopywritingOutput,
    DirectorOutput,
    ImageGenerationRequest,
    ResearchOutput,
    ReviewerOutput,
    StoryboardOutput,
    StrategyOutput,
    VideoPromptOutput,
    VideoTask,
)
from jhai_to_c.contracts.common import ProjectReference
from jhai_to_c.providers.interfaces import (
    AgentModelProvider,
    ImageProvider,
    ResearchProvider,
    VideoProvider,
)
from jhai_to_c.providers.mock.interfaces import (
    MockAgentModelProvider,
    MockResearchProvider,
    MockVideoProvider,
)
from jhai_to_c.workflow.state import ContentWorkflowState

CONTRACT_MODELS = (
    ContentProjectCreate,
    ContentProjectRead,
    CopywritingOutput,
    DirectorOutput,
    ImageGenerationRequest,
    ProjectReference,
    ResearchOutput,
    ReviewerOutput,
    StoryboardOutput,
    StrategyOutput,
    VideoPromptOutput,
    VideoTask,
)


def test_contracts_export_json_schema() -> None:
    for contract in CONTRACT_MODELS:
        schema = contract.model_json_schema()
        assert schema["type"] == "object"
        assert schema["title"] == contract.__name__


def test_contracts_reject_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        ContentProjectCreate(
            title="Demo",
            request_text="创建视频",
            unexpected=True,
        )


def test_workflow_state_contains_mvp_artifacts() -> None:
    fields = get_type_hints(ContentWorkflowState)
    expected = {
        "project_id",
        "creative_brief",
        "research",
        "strategies",
        "copywriting",
        "storyboard",
        "video_prompt",
        "review",
        "video_task",
    }
    assert expected <= fields.keys()


def test_provider_boundaries_are_protocols() -> None:
    protocols = (
        AgentModelProvider,
        ImageProvider,
        ResearchProvider,
        VideoProvider,
        MockAgentModelProvider,
        MockResearchProvider,
        MockVideoProvider,
    )
    assert all(getattr(provider, "_is_protocol", False) for provider in protocols)


def test_settings_have_safe_mock_defaults() -> None:
    settings = Settings(_env_file=None)
    assert settings.llm_provider == "mock"
    assert settings.research_provider == "mock"
    assert settings.video_provider == "mock"
    assert settings.image_provider == "disabled"
    assert settings.llm_api_key is None
    assert settings.video_api_key is None
    assert settings.image_api_key is None
    assert settings.resolved_auth_enabled is False


def test_authentication_can_be_enabled_explicitly() -> None:
    settings = Settings(_env_file=None, auth_enabled=True)
    assert settings.resolved_auth_enabled is True
