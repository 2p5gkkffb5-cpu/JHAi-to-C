from datetime import datetime
from enum import StrEnum

from pydantic import Field

from .common import ContractModel
from .strategy import StrategyOutput


class EvidenceType(StrEnum):
    USER_INPUT = "user_input"
    BRAND_FACT = "brand_fact"
    DEMO_SOURCE = "demo_source"
    EXTERNAL_SOURCE = "external_source"
    INFERENCE = "inference"


class ResearchSource(ContractModel):
    source_id: str = Field(min_length=1, max_length=128)
    title: str = Field(min_length=1, max_length=300)
    evidence_type: EvidenceType
    url: str | None = Field(default=None, max_length=2000)
    summary: str = Field(min_length=1, max_length=2000)
    retrieved_at: datetime | None = None


class ResearchInsight(ContractModel):
    claim: str = Field(min_length=1, max_length=1000)
    evidence_type: EvidenceType
    source_ids: list[str] = Field(default_factory=list, max_length=20)
    confidence: float = Field(ge=0, le=1)


class ResearchOutput(ContractModel):
    audience_insights: list[ResearchInsight] = Field(default_factory=list, max_length=20)
    competitor_patterns: list[str] = Field(default_factory=list, max_length=20)
    content_trends: list[str] = Field(default_factory=list, max_length=20)
    suggestions: list[str] = Field(default_factory=list, max_length=20)
    risk_notes: list[str] = Field(default_factory=list, max_length=20)
    sources: list[ResearchSource] = Field(default_factory=list, max_length=30)


class ResearchStrategyOutput(ContractModel):
    """Single-call output for evidence synthesis and strategy generation."""

    research: ResearchOutput
    strategies: StrategyOutput
