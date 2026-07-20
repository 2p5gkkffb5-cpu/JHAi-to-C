import pytest

from jhai_to_c.contracts.video import VideoTask
from jhai_to_c.providers.mock import (
    DeterministicMockAgentModelProvider,
    DeterministicMockResearchProvider,
    DeterministicMockVideoProvider,
    MockProviderControl,
)
from jhai_to_c.workflow import VideoGenerationNode, build_content_project_graph
from jhai_to_c.workflow.errors import InvalidReferenceSubsetError


class CaptureVideoProvider:
    provider_name = "capture"
    is_mock = True

    def __init__(self) -> None:
        self.request = None

    async def submit(self, *, request):
        self.request = request
        return VideoTask(
            task_id="captured",
            provider=self.provider_name,
            is_mock=True,
            status="completed",
            progress=1,
            result_url="https://example.com/result.mp4",
        )

    async def get_status(self, *, task_id):  # pragma: no cover - submit is terminal
        raise AssertionError(task_id)


def _initial_state() -> dict:
    return {
        "project_id": "workflow-unit-test",
        "request_text": "为一款便携咖啡机制作 20 秒短视频",
        "references": [],
        "target_platform": "douyin",
        "duration_seconds": 20,
        "aspect_ratio": "9:16",
        "completed_nodes": [],
        "provider_usage": {},
        "retry_count": 0,
        "errors": [],
    }


def _graph(scenario: str = "success"):
    control = MockProviderControl(latency_ms=0, scenario=scenario)
    return build_content_project_graph(
        agent_model_provider=DeterministicMockAgentModelProvider(control),
        research_provider=DeterministicMockResearchProvider(control),
        video_provider=DeterministicMockVideoProvider(control),
    )


@pytest.mark.asyncio
async def test_workflow_state_transitions_through_full_graph() -> None:
    updates = []
    final_state = _initial_state()
    async for update in _graph().astream(_initial_state(), stream_mode="updates"):
        node_name, state_update = next(iter(update.items()))
        updates.append(node_name)
        final_state.update(state_update)

    assert updates == [
        "director",
        "research",
        "production",
        "video_generation",
    ]
    assert final_state["completed_nodes"] == [
        "director",
        "research",
        "production",
        "video_generation",
    ]
    assert final_state["production_plan"]["production_goal"]
    assert [item["status"] for item in final_state["video_task_history"]] == [
        "queued",
        "processing",
        "completed",
    ]
    assert final_state["video_task"]["provider"] == "mock"


@pytest.mark.asyncio
async def test_legacy_review_fail_scenario_no_longer_blocks_video_generation() -> None:
    updates = []
    last_update = None
    async for update in _graph("review_fail").astream(_initial_state(), stream_mode="updates"):
        node_name, last_update = next(iter(update.items()))
        updates.append(node_name)

    assert updates[-1] == "video_generation"
    assert last_update is not None
    assert last_update["video_task"]["status"] == "completed"
    assert "review" not in last_update


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("reference_ids", "references", "expected_urls"),
    [
        (
            ["c", "a"],
            [
                {"id": "a", "snapshot": {"url": "https://example.com/a"}},
                {"id": "b", "snapshot": {"url": "https://example.com/b"}},
                {"id": "c", "snapshot": {"source_url": "https://example.com/c"}},
            ],
            ["https://example.com/a", "https://example.com/c"],
        ),
        (
            [],
            [{"id": "a", "snapshot": {"url": "https://example.com/a"}}],
            [],
        ),
        (
            ["a"],
            [
                {"id": "a", "snapshot": {}},
                {"id": "b", "snapshot": {"url": "https://example.com/b"}},
            ],
            [],
        ),
    ],
)
async def test_video_reference_urls_are_selected_and_original_ordered(
    reference_ids,
    references,
    expected_urls,
) -> None:
    provider = CaptureVideoProvider()
    state = {
        "project_id": "video-reference-test",
        "references": references,
        "review": {
            "status": "pass",
            "score": 90,
            "issues": [],
            "return_to": None,
            "required_changes": [],
        },
        "video_prompt": {
            "prompt": "生成产品短视频",
            "negative_prompt": "",
            "duration_seconds": 20,
            "aspect_ratio": "9:16",
            "reference_ids": reference_ids,
            "provider_parameters": {},
        },
        "completed_nodes": [],
        "provider_usage": {},
    }
    await VideoGenerationNode(provider)(state)
    assert provider.request.reference_urls == expected_urls


@pytest.mark.asyncio
async def test_video_reference_resolver_inlines_uploaded_assets() -> None:
    provider = CaptureVideoProvider()

    async def resolver(reference_id: str) -> str | None:
        if reference_id == "uploaded-image":
            return "data:image/png;base64,ZmFrZQ=="
        return None

    state = {
        "project_id": "video-inline-reference-test",
        "references": [
            {
                "id": "uploaded-image",
                "snapshot": {"url": "http://127.0.0.1/local.png"},
            },
            {
                "id": "remote-image",
                "snapshot": {"url": "https://assets.example.com/remote.png"},
            },
        ],
        "review": {
            "status": "pass",
            "score": 90,
            "issues": [],
            "return_to": None,
            "required_changes": [],
        },
        "video_prompt": {
            "prompt": "生成产品短视频",
            "negative_prompt": "",
            "duration_seconds": 15,
            "aspect_ratio": "9:16",
            "reference_ids": ["uploaded-image", "remote-image"],
            "provider_parameters": {},
        },
        "completed_nodes": [],
        "provider_usage": {},
    }

    await VideoGenerationNode(provider, reference_resolver=resolver)(state)

    assert provider.request.reference_urls == [
        "data:image/png;base64,ZmFrZQ==",
        "https://assets.example.com/remote.png",
    ]


@pytest.mark.asyncio
async def test_video_reference_unknown_id_fails_before_provider() -> None:
    provider = CaptureVideoProvider()
    state = {
        "project_id": "video-reference-invalid",
        "references": [],
        "review": {
            "status": "pass",
            "score": 90,
            "issues": [],
            "return_to": None,
            "required_changes": [],
        },
        "video_prompt": {
            "prompt": "生成产品短视频",
            "negative_prompt": "",
            "duration_seconds": 20,
            "aspect_ratio": "9:16",
            "reference_ids": ["unknown"],
            "provider_parameters": {},
        },
        "completed_nodes": [],
        "provider_usage": {},
    }
    with pytest.raises(InvalidReferenceSubsetError):
        await VideoGenerationNode(provider)(state)
    assert provider.request is None
