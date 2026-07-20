import shutil
import subprocess
from typing import Any, cast

import pytest
from pydantic import BaseModel

from jhai_to_c.providers.interfaces import StructuredGenerationResult
from jhai_to_c.providers.real.video_understanding import (
    FFmpegVideoUnderstandingProvider,
    _sample_timestamps,
)


class _TinyOutput(BaseModel):
    value: str


class _RecordingModel:
    provider_name = "test-model"
    is_mock = False

    def __init__(self, *, fail_first: bool = False) -> None:
        self.fail_first = fail_first
        self.calls: list[dict[str, Any]] = []

    async def generate_structured(self, **kwargs: Any) -> StructuredGenerationResult[Any]:
        self.calls.append(kwargs)
        if self.fail_first and len(self.calls) == 1:
            raise RuntimeError("native video transport failed")
        return StructuredGenerationResult(
            output=_TinyOutput(value="ok"),
            raw_output='{"value":"ok"}',
            provider=self.provider_name,
            model="test-model",
            duration_ms=1,
        )


def test_sample_timestamps_are_even_and_inside_the_video() -> None:
    assert _sample_timestamps(5) == [1.0, 2.0, 3.0, 4.0]
    assert _sample_timestamps(14) == [2.0, 4.0, 6.0, 8.0, 10.0, 12.0]


@pytest.mark.asyncio
async def test_ffmpeg_provider_reads_real_metadata_and_extracts_frames(tmp_path) -> None:
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if ffmpeg is None or ffprobe is None:
        pytest.skip("ffmpeg and ffprobe are required for this provider test")
    video_path = tmp_path / "sample.mp4"
    subprocess.run(
        [
            ffmpeg,
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=#c8683a:s=320x240:d=2",
            "-r",
            "24",
            "-pix_fmt",
            "yuv420p",
            "-y",
            str(video_path),
        ],
        check=True,
    )
    provider = FFmpegVideoUnderstandingProvider(
        asset_service=cast(Any, None),
        model_provider=cast(Any, None),
        max_download_bytes=10 * 1024 * 1024,
        ffmpeg_path=ffmpeg,
        ffprobe_path=ffprobe,
    )

    technical, frames = await provider._inspect(video_path)

    assert technical.duration_seconds == pytest.approx(2, abs=0.1)
    assert (technical.width, technical.height) == (320, 240)
    assert technical.fps == pytest.approx(24, abs=0.1)
    assert technical.has_audio is False
    assert len(technical.sampled_frame_seconds) == 4
    assert len(frames) == 1
    assert all(frame.startswith("data:image/jpeg;base64,") for frame in frames)


@pytest.mark.asyncio
async def test_native_video_is_sent_before_keyframes(tmp_path) -> None:
    video_path = tmp_path / "sample.mp4"
    video_path.write_bytes(b"small-video")
    model = _RecordingModel()
    provider = FFmpegVideoUnderstandingProvider(
        asset_service=cast(Any, None),
        model_provider=cast(Any, model),
        max_download_bytes=10 * 1024 * 1024,
        native_video_max_bytes=1024,
    )

    result, basis, warning = await provider._generate_with_native_fallback(
        path=video_path,
        mime_type="video/mp4",
        node="video_clone_analysis",
        system_prompt="analyze",
        input_data={
            "frame_order": [{"image_index": 1, "timestamp_seconds": 1.0}],
            "replacement_image_order": [
                {"image_index": 2, "reference_id": "replacement-1"}
            ],
        },
        output_model=_TinyOutput,
        image_urls=["data:image/jpeg;base64,ZmFrZQ=="],
    )

    assert result.output.value == "ok"
    assert basis == "gemini_native_video"
    assert warning is None
    assert model.calls[0]["metadata"]["image_urls"][0].startswith(
        "data:video/mp4;base64,"
    )
    assert model.calls[0]["input_data"]["frame_order"][0]["image_index"] == 2
    assert (
        model.calls[0]["input_data"]["replacement_image_order"][0]["image_index"]
        == 3
    )
    assert model.calls[0]["timeout_seconds"] == 60


@pytest.mark.asyncio
async def test_native_video_failure_falls_back_to_keyframes(tmp_path) -> None:
    video_path = tmp_path / "sample.mp4"
    video_path.write_bytes(b"small-video")
    model = _RecordingModel(fail_first=True)
    provider = FFmpegVideoUnderstandingProvider(
        asset_service=cast(Any, None),
        model_provider=cast(Any, model),
        max_download_bytes=10 * 1024 * 1024,
        native_video_max_bytes=1024,
    )
    frame_url = "data:image/jpeg;base64,ZmFrZQ=="

    _, basis, warning = await provider._generate_with_native_fallback(
        path=video_path,
        mime_type="video/mp4",
        node="video_clone_analysis",
        system_prompt="analyze",
        input_data={"frame_order": [{"image_index": 1, "timestamp_seconds": 1.0}]},
        output_model=_TinyOutput,
        image_urls=[frame_url],
    )

    assert basis == "ffmpeg_keyframes"
    assert warning == "原生视频输入失败，已回退关键帧（RuntimeError）"
    assert len(model.calls) == 2
    assert model.calls[1]["metadata"]["image_urls"] == [frame_url]
