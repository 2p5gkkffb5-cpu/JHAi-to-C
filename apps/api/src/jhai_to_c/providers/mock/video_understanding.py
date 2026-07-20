from jhai_to_c.contracts.video_clone import (
    VideoCloneAnalysisOutput,
    VideoCloneAnalysisRequest,
    VideoCloneReviewOutput,
    VideoCloneReviewRequest,
)

from .interfaces import MockProviderControl


class DeterministicMockVideoUnderstandingProvider:
    provider_name = "mock-video-understanding"
    is_mock = True

    def __init__(self, control: MockProviderControl | None = None) -> None:
        self.control = control or MockProviderControl()

    async def analyze(
        self,
        *,
        request: VideoCloneAnalysisRequest,
    ) -> VideoCloneAnalysisOutput:
        if self.control.scenario == "provider_error":
            raise RuntimeError("Mock video understanding error requested")
        midpoint = max(2.5, request.duration_seconds / 2)
        return VideoCloneAnalysisOutput.model_validate(
            {
                "analysis_basis": "mock_fixture",
                "reference_id": request.reference.id,
                "technical": {
                    "duration_seconds": request.duration_seconds,
                    "width": 1080 if request.aspect_ratio == "9:16" else 1920,
                    "height": 1920 if request.aspect_ratio == "9:16" else 1080,
                    "fps": 30,
                    "has_audio": True,
                    "sampled_frame_seconds": [0.5, midpoint, request.duration_seconds - 0.5],
                },
                "hook_summary": "前三秒用结果前置和快速动作建立反差，引导继续观看。",
                "narrative_structure": ["结果钩子", "问题放大", "产品演示", "证据强化", "行动引导"],
                "pacing_summary": "开场快切，中段用两段演示建立可信度，结尾收束 CTA。",
                "visual_style": "高对比近景、干净背景、主体始终占据视觉中心。",
                "audio_style": "节拍驱动剪辑，关键信息点使用短促音效强调。",
                "transferable_dna": [
                    "结果前置",
                    "每镜头只表达一个信息",
                    "动作点切镜",
                    "结尾明确 CTA",
                ],
                "protected_elements": ["不复用原视频人物肖像", "不照搬商标、台词和可识别布景"],
                "shots": [
                    {
                        "shot_id": "clone-shot-1",
                        "order": 1,
                        "start_seconds": 0,
                        "end_seconds": min(3, request.duration_seconds),
                        "purpose": "hook",
                        "visual_subject": "参考片主体与结果状态",
                        "action": "快速展示使用前后反差并立即给出结果",
                        "shot_size": "近景",
                        "camera_movement": "快速推进",
                        "dialogue_or_text": "先看结果",
                        "transition": "动作匹配切镜",
                        "reusable_pattern": "结果前置 + 反差 + 一句话承诺",
                    },
                    {
                        "shot_id": "clone-shot-2",
                        "order": 2,
                        "start_seconds": min(3, request.duration_seconds - 1),
                        "end_seconds": request.duration_seconds,
                        "purpose": "selling_point",
                        "visual_subject": "参考片核心演示对象",
                        "action": "连续完成核心演示并在结尾给出行动提示",
                        "shot_size": "中近景与特写交替",
                        "camera_movement": "稳定跟随",
                        "dialogue_or_text": "核心卖点与行动引导",
                        "transition": "节拍切镜",
                        "reusable_pattern": "动作演示 + 细节证据 + CTA",
                    },
                ],
                "warnings": ["当前为 Mock 解析结果，仅用于开发与流程验证。"],
            }
        )

    async def review(
        self,
        *,
        request: VideoCloneReviewRequest,
    ) -> VideoCloneReviewOutput:
        del request
        return VideoCloneReviewOutput.model_validate(
            {
                "status": "pass",
                "score": 90,
                "analysis_basis": "mock_fixture",
                "checks": [
                    {
                        "name": "结构匹配",
                        "status": "pass",
                        "evidence": "钩子、演示和 CTA 节点齐全。",
                    },
                    {
                        "name": "素材替换",
                        "status": "pass",
                        "evidence": "逐镜头提示词均绑定替换素材。",
                    },
                    {"name": "生成完成", "status": "pass", "evidence": "视频任务已返回完成状态。"},
                ],
                "differences": ["主体、场景与文案已按用户素材重写。"],
                "repair_suggestions": [],
            }
        )
