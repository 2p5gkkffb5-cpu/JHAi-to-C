from __future__ import annotations

import asyncio
import base64
import json
import shutil
import tempfile
from fractions import Fraction
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel

from jhai_to_c.contracts.common import ProjectReference
from jhai_to_c.contracts.video_clone import (
    VideoCloneAnalysisOutput,
    VideoCloneAnalysisRequest,
    VideoCloneReviewOutput,
    VideoCloneReviewRequest,
    VideoTechnicalProfile,
)
from jhai_to_c.providers.interfaces import AgentModelProvider, StructuredGenerationResult
from jhai_to_c.services.asset import UploadedAssetService


class VideoUnderstandingError(RuntimeError):
    pass


_NATIVE_VIDEO_MIME_TYPES = frozenset(
    {
        "video/mp4",
        "video/mpeg",
        "video/quicktime",
        "video/x-msvideo",
        "video/webm",
        "video/3gpp",
    }
)


class FFmpegVideoUnderstandingProvider:
    provider_name = "ffmpeg-keyframes"
    is_mock = False

    def __init__(
        self,
        *,
        asset_service: UploadedAssetService,
        model_provider: AgentModelProvider,
        max_download_bytes: int,
        native_video_enabled: bool = True,
        native_video_max_bytes: int = 20 * 1024 * 1024,
        native_video_timeout_seconds: int = 60,
        ffprobe_path: str = "ffprobe",
        ffmpeg_path: str = "ffmpeg",
    ) -> None:
        if native_video_max_bytes <= 0:
            raise ValueError("native_video_max_bytes must be greater than zero")
        if native_video_timeout_seconds <= 0:
            raise ValueError("native_video_timeout_seconds must be greater than zero")
        self.asset_service = asset_service
        self.model_provider = model_provider
        self.max_download_bytes = max_download_bytes
        self.native_video_enabled = native_video_enabled
        self.native_video_max_bytes = native_video_max_bytes
        self.native_video_timeout_seconds = native_video_timeout_seconds
        self.provider_name = (
            "gemini-video+ffmpeg" if native_video_enabled else "ffmpeg-keyframes"
        )
        self.ffprobe_path = ffprobe_path
        self.ffmpeg_path = ffmpeg_path

    async def analyze(
        self,
        *,
        request: VideoCloneAnalysisRequest,
    ) -> VideoCloneAnalysisOutput:
        asset = await self.asset_service.get(request.reference.id)
        if asset is None or asset.asset_type != "video":
            raise VideoUnderstandingError("参考视频不是当前项目已上传的视频资产")
        path = self.asset_service.path_for(asset.storage_key)
        if not path.is_file():
            raise VideoUnderstandingError("参考视频文件不存在")
        technical, image_urls = await self._inspect(path)
        result, analysis_basis, fallback_warning = (
            await self._generate_with_native_fallback(
                path=path,
                mime_type=asset.content_type,
                node="video_clone_analysis",
                system_prompt=_ANALYSIS_PROMPT,
                input_data={
                    "request": request.model_dump(mode="json"),
                    "technical": technical.model_dump(mode="json"),
                    "frame_order": [
                        {
                            "image_index": 1,
                            "panel_index": index + 1,
                            "timestamp_seconds": timestamp,
                        }
                        for index, timestamp in enumerate(
                            technical.sampled_frame_seconds
                        )
                    ],
                },
                output_model=VideoCloneAnalysisOutput,
                image_urls=image_urls,
            )
        )
        payload = result.output.model_dump(mode="json")
        payload.update(
            {
                "analysis_basis": analysis_basis,
                "reference_id": request.reference.id,
                "technical": technical.model_dump(mode="json"),
            }
        )
        if fallback_warning is not None:
            payload["warnings"] = [*payload.get("warnings", []), fallback_warning]
        return VideoCloneAnalysisOutput.model_validate(payload)

    async def review(
        self,
        *,
        request: VideoCloneReviewRequest,
    ) -> VideoCloneReviewOutput:
        parsed = urlparse(request.result_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise VideoUnderstandingError("生成视频结果地址不是有效的 HTTP(S) URL")
        with tempfile.TemporaryDirectory(prefix="jhai-video-review-") as directory:
            target = Path(directory) / "generated-video.mp4"
            await self._download(request.result_url, target)
            technical, image_urls = await self._inspect(target)
            replacement_images = await self._replacement_images(
                request.replacement_references
            )
            replacement_order = [
                {
                    "image_index": len(image_urls) + index + 1,
                    "reference_id": reference_id,
                }
                for index, (reference_id, _) in enumerate(replacement_images)
            ]
            result, analysis_basis, fallback_warning = (
                await self._generate_with_native_fallback(
                    path=target,
                    mime_type="video/mp4",
                    node="video_clone_review",
                    system_prompt=_REVIEW_PROMPT,
                    input_data={
                        "expected": request.model_dump(
                            mode="json", exclude={"result_url"}
                        ),
                        "generated_technical": technical.model_dump(mode="json"),
                        "frame_order": [
                            {
                                "image_index": 1,
                                "panel_index": index + 1,
                                "timestamp_seconds": timestamp,
                            }
                            for index, timestamp in enumerate(
                                technical.sampled_frame_seconds
                            )
                        ],
                        "replacement_image_order": replacement_order,
                    },
                    output_model=VideoCloneReviewOutput,
                    image_urls=[
                        *image_urls,
                        *[url for _, url in replacement_images],
                    ],
                )
            )
        payload = result.output.model_dump(mode="json")
        payload["analysis_basis"] = analysis_basis
        if fallback_warning is not None:
            payload["differences"] = [
                *payload.get("differences", []),
                fallback_warning,
            ]
        return VideoCloneReviewOutput.model_validate(payload)

    async def _generate_with_native_fallback[OutputT: BaseModel](
        self,
        *,
        path: Path,
        mime_type: str,
        node: str,
        system_prompt: str,
        input_data: dict[str, Any],
        output_model: type[OutputT],
        image_urls: list[str],
    ) -> tuple[StructuredGenerationResult[OutputT], str, str | None]:
        native_url, skip_warning = await self._native_video_data_url(path, mime_type)
        if native_url is None:
            result = await self.model_provider.generate_structured(
                system_prompt=system_prompt,
                input_data=input_data,
                output_model=output_model,
                metadata={"node": node, "image_urls": image_urls},
            )
            return result, "ffmpeg_keyframes", skip_warning

        native_input_data = dict(input_data)
        native_input_data["native_video_input"] = {
            "included": True,
            "mime_type": mime_type,
        }
        for order_field in ("frame_order", "replacement_image_order"):
            order = native_input_data.get(order_field)
            if isinstance(order, list):
                native_input_data[order_field] = [
                    {
                        **item,
                        "image_index": item.get("image_index", index + 1) + 1,
                    }
                    if isinstance(item, dict)
                    else item
                    for index, item in enumerate(order)
                ]
        try:
            result = await self.model_provider.generate_structured(
                system_prompt=system_prompt,
                input_data=native_input_data,
                output_model=output_model,
                timeout_seconds=self.native_video_timeout_seconds,
                metadata={"node": node, "image_urls": [native_url, *image_urls]},
            )
            return result, "gemini_native_video", None
        except RuntimeError as exc:
            result = await self.model_provider.generate_structured(
                system_prompt=system_prompt,
                input_data=input_data,
                output_model=output_model,
                metadata={"node": node, "image_urls": image_urls},
            )
            warning = f"原生视频输入失败，已回退关键帧（{type(exc).__name__}）"
            return result, "ffmpeg_keyframes", warning

    async def _native_video_data_url(
        self,
        path: Path,
        mime_type: str,
    ) -> tuple[str | None, str | None]:
        if not self.native_video_enabled:
            return None, None
        if mime_type not in _NATIVE_VIDEO_MIME_TYPES:
            return None, f"视频格式 {mime_type} 不支持原生输入，已使用关键帧"
        size = path.stat().st_size
        if size > self.native_video_max_bytes:
            return None, (
                "视频超过原生输入大小限制，已使用关键帧"
                f"（{size} > {self.native_video_max_bytes} bytes）"
            )
        video = await asyncio.to_thread(path.read_bytes)
        encoded = base64.b64encode(video).decode("ascii")
        return f"data:{mime_type};base64,{encoded}", None

    async def _replacement_images(
        self,
        references: list[ProjectReference],
    ) -> list[tuple[str, str]]:
        images: list[tuple[str, str]] = []
        for reference in references:
            data_url = await self.asset_service.inline_image_data_url(reference.id)
            if data_url is not None:
                images.append((reference.id, data_url))
                continue
            url = reference.snapshot.get("url") or reference.snapshot.get("source_url")
            if isinstance(url, str) and url.startswith(("http://", "https://")):
                images.append((reference.id, url))
        return images

    async def _inspect(self, path: Path) -> tuple[VideoTechnicalProfile, list[str]]:
        self._ensure_tools()
        probe = await _run_process(
            self.ffprobe_path,
            "-v",
            "error",
            "-show_streams",
            "-show_format",
            "-of",
            "json",
            str(path),
        )
        try:
            payload = json.loads(probe.decode("utf-8"))
            streams = payload.get("streams", [])
            video_stream = next(item for item in streams if item.get("codec_type") == "video")
            duration = float(
                payload.get("format", {}).get("duration") or video_stream.get("duration")
            )
            frame_rate = Fraction(video_stream.get("avg_frame_rate") or "0/1")
            fps = float(frame_rate)
            if duration <= 0 or fps <= 0:
                raise ValueError("invalid duration or frame rate")
            timestamps = _sample_timestamps(duration)
            technical = VideoTechnicalProfile(
                duration_seconds=duration,
                width=int(video_stream["width"]),
                height=int(video_stream["height"]),
                fps=fps,
                has_audio=any(item.get("codec_type") == "audio" for item in streams),
                sampled_frame_seconds=timestamps,
            )
        except (KeyError, StopIteration, TypeError, ValueError, ZeroDivisionError) as exc:
            raise VideoUnderstandingError("无法从视频中读取有效的技术参数") from exc

        contact_sheet = await self._extract_contact_sheet(
            path,
            duration=technical.duration_seconds,
            frame_count=len(timestamps),
        )
        return technical, [
            "data:image/jpeg;base64,"
            + base64.b64encode(contact_sheet).decode("ascii")
        ]

    async def _extract_contact_sheet(
        self,
        path: Path,
        *,
        duration: float,
        frame_count: int,
    ) -> bytes:
        step = duration / (frame_count + 1)
        columns = 2 if frame_count <= 4 else 3
        rows = (frame_count + columns - 1) // columns
        return await _run_process(
            self.ffmpeg_path,
            "-v",
            "error",
            "-ss",
            f"{step:.3f}",
            "-i",
            str(path),
            "-vf",
            (
                f"fps={1 / step:.8f},scale='min(360,iw)':-2,"
                f"tile={columns}x{rows}:nb_frames={frame_count}:padding=4:margin=4"
            ),
            "-frames:v",
            "1",
            "-f",
            "image2pipe",
            "-vcodec",
            "mjpeg",
            "pipe:1",
        )

    async def _download(self, url: str, target: Path) -> None:
        total = 0
        async with httpx.AsyncClient(follow_redirects=True, timeout=60) as client:
            async with client.stream("GET", url) as response:
                response.raise_for_status()
                with target.open("wb") as file:
                    async for chunk in response.aiter_bytes():
                        total += len(chunk)
                        if total > self.max_download_bytes:
                            raise VideoUnderstandingError("生成视频超过验收下载大小限制")
                        file.write(chunk)
        if total == 0:
            raise VideoUnderstandingError("生成视频内容为空")

    def _ensure_tools(self) -> None:
        if shutil.which(self.ffprobe_path) is None or shutil.which(self.ffmpeg_path) is None:
            raise VideoUnderstandingError("视频解析需要安装 ffprobe 和 ffmpeg")


async def _run_process(*arguments: str) -> bytes:
    process = await asyncio.create_subprocess_exec(
        *arguments,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        detail = stderr.decode("utf-8", errors="replace").strip()[-1000:]
        raise VideoUnderstandingError(f"视频解析命令失败：{detail or process.returncode}")
    if not stdout:
        raise VideoUnderstandingError("视频解析命令没有返回内容")
    return stdout


def _sample_timestamps(duration: float) -> list[float]:
    frame_count = 6 if duration >= 10 else 4
    return [round(duration * (index + 1) / (frame_count + 1), 3) for index in range(frame_count)]


_ANALYSIS_PROMPT = """
你是视频复刻分析师。输入包含视频真实技术参数，以及一张按从左到右、从上到下排列的
关键帧联系表；frame_order.panel_index 表示格子序号。当
native_video_input.included=true 时，还包含原始视频及其音频。综合这些证据拆解钩子、
叙事节奏、镜头语言、字幕/台词线索与可迁移的视频 DNA。原始视频未提供时，不要声称
看到了关键帧之外的内容；不确定的信息写入 warnings。
逐镜头时间必须在视频总时长内，禁止复制人物肖像、商标、独特台词或可识别布景。
原始视频已提供时 analysis_basis 填写 gemini_native_video，否则填写 ffmpeg_keyframes。
""".strip()

_REVIEW_PROMPT = """
你是视频复刻验收员。输入包含原片分析、素材映射、生成提示词、生成视频技术参数，
以及一张按从左到右、从上到下排列的生成视频关键帧联系表；frame_order.panel_index
表示格子序号。当 native_video_input.included=true 时，还包含完整
生成视频及其音频。replacement_image_order 将替换素材 ID 映射到对应输入图片，必须用这些
真实像素判断主体一致性，不得仅根据文件名、颜色描述或提示词推测。检查结构匹配、素材替换、
主体一致性、镜头完整性、字幕/品牌风险和
明显生成缺陷。证据只能来自已提供的输入；无法确认时标记 warning。原始视频已提供时
analysis_basis 填写 gemini_native_video，否则填写 ffmpeg_keyframes。
""".strip()
