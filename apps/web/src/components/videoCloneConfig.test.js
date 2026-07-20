import { describe, expect, it } from "vitest";
import { buildVideoCloneRequest } from "./videoCloneConfig.js";

describe("buildVideoCloneRequest", () => {
  it("builds a structured workflow request", () => {
    const prompt = buildVideoCloneRequest({
      cloneLevel: "平衡复刻",
      goal: "替换成我的新品卖点",
      referenceFilename: "参考.mp4",
      replacementFilenames: ["新品.png"],
    });

    expect(prompt).toContain("【视频复刻输入】");
    expect(prompt).not.toContain("内容类型：");
    expect(prompt).toContain("发布平台：抖音");
    expect(prompt).toContain("复刻强度：平衡复刻");
    expect(prompt).toContain("改编目标：替换成我的新品卖点");
    expect(prompt).toContain("参考样片：@参考.mp4");
    expect(prompt).toContain("替换素材：@新品.png");
    expect(prompt).toContain("解析参考样片 → 映射替换素材 → 优化逐镜头提示词 → 生成并验收");
  });

  it("uses a useful default goal when the brief is empty", () => {
    const prompt = buildVideoCloneRequest({
      cloneLevel: "结构借鉴",
      goal: "   ",
      referenceFilename: "口播.mp4",
      replacementFilenames: ["人物.png"],
    });

    expect(prompt).toContain("复刻参考视频的高转化结构");
  });
});
