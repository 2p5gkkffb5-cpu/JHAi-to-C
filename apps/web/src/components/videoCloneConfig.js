export const videoCloneTargetPlatform = { value: "douyin", label: "抖音" };

export const videoCloneLevels = [
  { value: "结构借鉴", description: "只保留钩子与叙事骨架，原创差异最大" },
  { value: "平衡复刻", description: "保留节奏和镜头逻辑，重做素材与文案" },
  { value: "高还原", description: "尽量贴近视听节奏，需确认素材使用授权" },
];

export const videoCloneSteps = [
  ["01", "输入样片", "参考视频 + 替换素材"],
  ["02", "拆解爆点", "钩子、节奏、镜头、台词"],
  ["03", "合规改编", "换主体、换场景、换表达"],
  ["04", "生成验收", "成片与复刻检查"],
];

export function buildVideoCloneRequest({
  cloneLevel,
  goal,
  referenceFilename,
  replacementFilenames,
}) {
  const cleanGoal = goal.trim() || "复刻参考视频的高转化结构，并保持替换主体与品牌信息准确";
  const replacements = replacementFilenames.map((filename) => `@${filename}`).join("、");
  return [
    "【视频复刻输入】",
    `参考样片：@${referenceFilename}`,
    `替换素材：${replacements}`,
    `发布平台：${videoCloneTargetPlatform.label}`,
    `复刻强度：${cloneLevel}`,
    `改编目标：${cleanGoal}`,
    "处理方式：解析参考样片 → 映射替换素材 → 优化逐镜头提示词 → 生成并验收。",
  ].join("\n");
}
