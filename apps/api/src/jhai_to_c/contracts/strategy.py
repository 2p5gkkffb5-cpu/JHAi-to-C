from pydantic import Field

from .common import ContractModel


class StrategyScores(ContractModel):
    brand_fit: int = Field(ge=0, le=100)
    conversion_fit: int = Field(ge=0, le=100)
    execution_feasibility: int = Field(ge=0, le=100)
    differentiation: int = Field(ge=0, le=100)


class StrategyOption(ContractModel):
    strategy_id: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=100)
    summary: str = Field(min_length=1, max_length=1000)
    target_audience: str = Field(min_length=1, max_length=500)
    core_message: str = Field(min_length=1, max_length=500)
    selling_points: list[str] = Field(min_length=1, max_length=10)
    hook: str = Field(min_length=1, max_length=500)
    narrative_structure: list[str] = Field(min_length=1, max_length=10)
    visual_direction: str = Field(min_length=1, max_length=1000)
    cta: str = Field(min_length=1, max_length=500)
    risks: list[str] = Field(default_factory=list, max_length=10)
    scores: StrategyScores


class StrategyOutput(ContractModel):
    strategy_options: list[StrategyOption] = Field(min_length=3, max_length=3)
    recommended_strategy_id: str = Field(min_length=1, max_length=128)
    recommendation_reason: str = Field(min_length=1, max_length=1000)
