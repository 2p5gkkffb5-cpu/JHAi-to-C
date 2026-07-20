import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { VideoCloneOutputs } from "./VideoCloneOutputs.jsx";

describe("VideoCloneOutputs", () => {
  it("shows structured analysis, mapping, prompt and review artifacts", () => {
    render(<VideoCloneOutputs current={{
      status: "completed",
      current_node: null,
      artifacts: {
        video_clone_analysis: {
          analysis_basis: "ffmpeg_keyframes",
          technical: { duration_seconds: 10, width: 1080, height: 1920 },
          hook_summary: "结果前置钩子",
          pacing_summary: "前三秒快切",
          transferable_dna: ["动作点切镜"],
          shots: [{ shot_id: "shot-1", start_seconds: 0, end_seconds: 3, reusable_pattern: "反差钩子" }],
        },
        video_clone_mapping: {
          strategy: "换主体、换场景、换表达",
          continuity_rules: ["商品外观一致"],
          mappings: [{ shot_id: "shot-1", rewritten_subject: "新品咖啡机", rewritten_action: "展示萃取" }],
        },
        video_clone_prompt: {
          optimization_summary: "已优化时间轴",
          shot_prompts: [{ shot_id: "shot-1", prompt: "近景展示咖啡萃取" }],
          generation: { prompt: "0-3 秒近景展示咖啡萃取" },
        },
        video_clone_review: {
          status: "pass",
          score: 92,
          checks: [{ name: "结构匹配", status: "pass", evidence: "钩子完整" }],
          repair_suggestions: [],
        },
      },
    }} />);

    expect(screen.getByText("复刻执行单")).toBeInTheDocument();
    expect(screen.getByText("FFmpeg 关键帧")).toBeInTheDocument();
    expect(screen.getByText("结果前置钩子")).toBeInTheDocument();
    expect(screen.getByText("换主体、换场景、换表达")).toBeInTheDocument();
    expect(screen.getByText("近景展示咖啡萃取")).toBeInTheDocument();
    expect(screen.getByText("92")).toBeInTheDocument();
  });

  it("labels native Gemini video analysis without treating it as mock", () => {
    render(<VideoCloneOutputs current={{
      status: "running",
      current_node: null,
      artifacts: {
        video_clone_analysis: {
          analysis_basis: "gemini_native_video",
          technical: { duration_seconds: 5, width: 720, height: 1280 },
          hook_summary: "原生视频钩子",
          pacing_summary: "连续运动",
          transferable_dna: [],
          shots: [],
        },
      },
    }} />);

    expect(screen.getByText("Gemini 原生视频 + 关键帧")).toBeInTheDocument();
    expect(screen.queryByText("Mock 演示")).not.toBeInTheDocument();
  });
});
