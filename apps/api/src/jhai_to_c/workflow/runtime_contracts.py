from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ValidationError

from jhai_to_c.contracts.director import DirectorOutput
from jhai_to_c.contracts.packaging import BrandPackagingOutput
from jhai_to_c.contracts.production import ProductionPackageOutput
from jhai_to_c.contracts.research import ResearchStrategyOutput
from jhai_to_c.contracts.video_clone import (
    VideoCloneAnalysisOutput,
    VideoCloneMappingOutput,
    VideoClonePromptOutput,
    VideoCloneReviewOutput,
)

from .production import validate_production_package


@dataclass(frozen=True, slots=True)
class AgentOutputSpec:
    result_key: str
    output_model: type[BaseModel]
    agent_name: str


AGENT_OUTPUT_SPECS: dict[str, AgentOutputSpec] = {
    "director": AgentOutputSpec("director", DirectorOutput, "director"),
    "research": AgentOutputSpec("research_strategy", ResearchStrategyOutput, "research"),
    "production": AgentOutputSpec("production", ProductionPackageOutput, "production"),
    "brand_packaging": AgentOutputSpec("brand_packaging", BrandPackagingOutput, "brand_packaging"),
    "video_clone_analysis": AgentOutputSpec(
        "video_clone_analysis", VideoCloneAnalysisOutput, "video_clone_analysis"
    ),
    "video_clone_mapping": AgentOutputSpec(
        "video_clone_mapping", VideoCloneMappingOutput, "video_clone_mapping"
    ),
    "video_clone_prompt": AgentOutputSpec(
        "video_clone_prompt", VideoClonePromptOutput, "video_clone_prompt"
    ),
    "video_clone_review": AgentOutputSpec(
        "video_clone_review", VideoCloneReviewOutput, "video_clone_review"
    ),
}


class AgentOutputExtractionError(ValueError):
    code = "invalid_agent_output"

    def __init__(self, node_name: str, reason: str) -> None:
        self.node_name = node_name
        self.reason = reason
        super().__init__(f"{self.code}: {node_name}: {reason}")


def extract_agent_output(
    node_name: str,
    result: object,
    *,
    agent_input: BaseModel | None = None,
) -> dict[str, Any]:
    spec = AGENT_OUTPUT_SPECS.get(node_name)
    if spec is None:
        raise AgentOutputExtractionError(node_name, "missing output spec")
    if not isinstance(result, Mapping):
        raise AgentOutputExtractionError(node_name, "task result is not an object")
    value = result.get(spec.result_key)
    if not isinstance(value, Mapping):
        raise AgentOutputExtractionError(
            node_name,
            f"result key '{spec.result_key}' is missing or is not an object",
        )
    try:
        output = spec.output_model.model_validate(value)
    except ValidationError as exc:
        raise AgentOutputExtractionError(node_name, "output schema validation failed") from exc
    if node_name == "production":
        if agent_input is None:
            raise AgentOutputExtractionError(node_name, "validated agent input is unavailable")
        validate_production_package(output, agent_input)
    return output.model_dump(mode="json")


def parse_agent_run_output(node_name: str, output_data: object) -> BaseModel:
    """Read Phase C bodies first, then the Phase A/B result envelope."""

    spec = AGENT_OUTPUT_SPECS[node_name]
    try:
        return spec.output_model.model_validate(output_data)
    except ValidationError as direct_error:
        if isinstance(output_data, Mapping) and spec.result_key in output_data:
            return spec.output_model.model_validate(output_data[spec.result_key])
        raise direct_error
