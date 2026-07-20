from typing import Protocol

from pydantic import Field

from jhai_to_c.contracts.common import ContractModel
from jhai_to_c.providers.interfaces import (
    AgentModelProvider,
    ResearchProvider,
    VideoProvider,
)


class MockProviderControl(ContractModel):
    latency_ms: int = Field(default=250, ge=0, le=30_000)
    scenario: str = Field(default="success", min_length=1, max_length=100)
    fixture_name: str | None = Field(default=None, max_length=200)


class MockAgentModelProvider(AgentModelProvider, Protocol):
    control: MockProviderControl


class MockResearchProvider(ResearchProvider, Protocol):
    control: MockProviderControl


class MockVideoProvider(VideoProvider, Protocol):
    control: MockProviderControl
