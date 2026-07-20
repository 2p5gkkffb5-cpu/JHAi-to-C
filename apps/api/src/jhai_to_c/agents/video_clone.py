from pydantic import Field

from jhai_to_c.contracts.common import ContractModel, ProjectReference
from jhai_to_c.contracts.video_clone import (
    VideoCloneAnalysisOutput,
    VideoCloneMappingOutput,
    VideoClonePromptOutput,
)
from jhai_to_c.prompts import PromptLoader
from jhai_to_c.providers.interfaces import AgentModelProvider


class VideoCloneMappingInput(ContractModel):
    request_text: str = Field(min_length=1, max_length=5000)
    analysis: VideoCloneAnalysisOutput
    replacement_references: list[ProjectReference] = Field(min_length=1, max_length=10)
    target_platform: str = Field(min_length=1, max_length=50)


class VideoClonePromptInput(ContractModel):
    request_text: str = Field(min_length=1, max_length=5000)
    analysis: VideoCloneAnalysisOutput
    mapping: VideoCloneMappingOutput
    references: list[ProjectReference] = Field(min_length=2, max_length=11)
    duration_seconds: int = Field(ge=5, le=180)
    aspect_ratio: str = Field(pattern=r"^(9:16|16:9|1:1)$")


class VideoCloneMappingAgent:
    def __init__(self, provider: AgentModelProvider, *, system_prompt: str | None = None) -> None:
        self.provider = provider
        self.system_prompt = system_prompt or PromptLoader().load("video_clone_mapping")

    async def execute(
        self,
        input_data: VideoCloneMappingInput,
        *,
        reference_images: list[tuple[str, str]] | None = None,
    ) -> VideoCloneMappingOutput:
        images = reference_images or []
        payload = input_data.model_dump(mode="json")
        if images:
            payload["replacement_image_order"] = [
                {"image_index": index + 1, "reference_id": reference_id}
                for index, (reference_id, _) in enumerate(images)
            ]
        result = await self.provider.generate_structured(
            system_prompt=self.system_prompt,
            input_data=payload,
            output_model=VideoCloneMappingOutput,
            metadata={
                "agent": "video_clone_mapping",
                "node": "video_clone_mapping",
                "image_urls": [url for _, url in images],
            },
        )
        return result.output


class VideoClonePromptAgent:
    def __init__(self, provider: AgentModelProvider, *, system_prompt: str | None = None) -> None:
        self.provider = provider
        self.system_prompt = system_prompt or PromptLoader().load("video_clone_prompt")

    async def execute(
        self,
        input_data: VideoClonePromptInput,
        *,
        reference_images: list[tuple[str, str]] | None = None,
    ) -> VideoClonePromptOutput:
        images = reference_images or []
        payload = input_data.model_dump(mode="json")
        if images:
            payload["replacement_image_order"] = [
                {"image_index": index + 1, "reference_id": reference_id}
                for index, (reference_id, _) in enumerate(images)
            ]
        result = await self.provider.generate_structured(
            system_prompt=self.system_prompt,
            input_data=payload,
            output_model=VideoClonePromptOutput,
            metadata={
                "agent": "video_clone_prompt",
                "node": "video_clone_prompt",
                "image_urls": [url for _, url in images],
            },
        )
        output = result.output
        replacement_ids = list(input_data.mapping.replacement_reference_ids)
        selected_ids = [
            reference_id
            for reference_id in output.generation.reference_ids
            if reference_id in replacement_ids
        ]
        if not selected_ids:
            selected_ids = replacement_ids
        reference_labels = {
            reference_id: f"参考图 {index + 1}"
            for index, reference_id in enumerate(replacement_ids)
        }
        parameters = dict(output.generation.provider_parameters)
        parameters.setdefault("resolution", "1080p")
        parameters.setdefault("generate_audio", False)
        parameters.setdefault("watermark", False)
        parameters.setdefault("return_last_frame", True)
        parameters.setdefault("camera_fixed", _all_shots_are_static(input_data.analysis))
        generation = output.generation.model_copy(
            update={
                "prompt": _replace_reference_ids(
                    output.generation.prompt, reference_labels
                ),
                "negative_prompt": _replace_reference_ids(
                    output.generation.negative_prompt, reference_labels
                ),
                "reference_ids": selected_ids,
                "provider_parameters": parameters,
            }
        )
        mappings_by_shot = {
            mapping.shot_id: mapping.replacement_reference_ids
            for mapping in input_data.mapping.mappings
        }
        shot_prompts = []
        for shot_prompt in output.shot_prompts:
            shot_reference_ids = [
                reference_id
                for reference_id in shot_prompt.reference_ids
                if reference_id in selected_ids
            ]
            if not shot_reference_ids:
                shot_reference_ids = [
                    reference_id
                    for reference_id in mappings_by_shot.get(shot_prompt.shot_id, [])
                    if reference_id in selected_ids
                ]
            shot_prompts.append(
                shot_prompt.model_copy(
                    update={
                        "prompt": _replace_reference_ids(
                            shot_prompt.prompt, reference_labels
                        ),
                        "negative_prompt": _replace_reference_ids(
                            shot_prompt.negative_prompt, reference_labels
                        ),
                        "reference_ids": shot_reference_ids or selected_ids,
                    }
                )
            )
        return output.model_copy(
            update={
                "optimization_summary": _replace_reference_ids(
                    output.optimization_summary, reference_labels
                ),
                "shot_prompts": shot_prompts,
                "generation": generation,
            }
        )


def _all_shots_are_static(analysis: VideoCloneAnalysisOutput) -> bool:
    static_markers = ("static", "locked", "固定", "静止", "无运镜")
    return all(
        any(marker in shot.camera_movement.lower() for marker in static_markers)
        for shot in analysis.shots
    )


def _replace_reference_ids(text: str, labels: dict[str, str]) -> str:
    for reference_id, label in labels.items():
        text = text.replace(reference_id, label)
    return text
