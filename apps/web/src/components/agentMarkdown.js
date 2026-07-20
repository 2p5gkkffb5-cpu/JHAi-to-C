const SECTION_TITLES = {
  strategy: "内容策略",
  copywriting: "完整文案",
  storyboard: "分镜脚本",
  video_prompt: "视频生成说明",
  review: "交付前检查",
  video_task: "视频成片",
  creative_brief: "创作方向",
  research: "受众与内容洞察",
  strategies: "备选策略",
  production_plan: "制作安排",
  brand_packaging: "一站式包装方案",
};

const FIELD_LABELS = {
  product: "产品",
  industry: "行业",
  goal: "创作目标",
  target_audience: "想打动的人",
  platform: "发布平台",
  duration_seconds: "时长（秒）",
  total_duration_seconds: "总时长（秒）",
  estimated_duration_seconds: "预计时长（秒）",
  aspect_ratio: "画面比例",
  content_direction: "内容方向",
  tone: "表达语气",
  must_include: "一定要表达",
  must_avoid: "需要避开",
  assumptions: "当前假设",
  missing_fields: "还可以补充",
  audience_insights: "受众洞察",
  competitor_patterns: "常见内容路径",
  content_trends: "内容趋势",
  suggestions: "行动建议",
  risk_notes: "温馨提醒",
  sources: "参考来源",
  strategy_options: "可选方向",
  recommended_strategy_id: "推荐方向",
  recommendation_reason: "推荐理由",
  name: "方向名称",
  summary: "方向说明",
  audience: "核心受众",
  hook: "开场钩子",
  message: "核心表达",
  structure: "内容结构",
  visual_direction: "视觉方向",
  title: "标题",
  voiceover: "完整旁白",
  onscreen_text: "屏幕文字",
  cta: "行动引导",
  continuity_rules: "画面连贯规则",
  visual_style: "视觉风格",
  shots: "镜头安排",
  shot_id: "镜头编号",
  order: "顺序",
  start_seconds: "开始时间（秒）",
  end_seconds: "结束时间（秒）",
  purpose: "镜头作用",
  visual: "画面内容",
  subject: "画面主体",
  action: "主体动作",
  camera: "镜头语言",
  shot_size: "景别",
  angle: "角度",
  movement: "运镜",
  transition: "转场",
  generation_prompt: "画面生成描述",
  prompt: "视频生成描述",
  negative_prompt: "需要避免的画面",
  status: "状态",
  progress: "生成进度",
  score: "完成度评分",
  issues: "发现的问题",
  required_changes: "需要调整",
  result_url: "成片地址",
  production_goal: "制作目标",
  copywriting_instruction: "文案要求",
  storyboard_instruction: "分镜要求",
  video_prompt_instruction: "视频生成要求",
  claim: "洞察",
  confidence: "把握程度",
  evidence_type: "依据类型",
  url: "查看来源",
  text: "文字",
  executive_summary: "方案摘要",
  package_type: "包装类型",
  brand_foundation: "品牌基础",
  brand_name: "品牌名称",
  positioning: "品牌定位",
  value_proposition: "核心价值",
  slogan: "品牌口号",
  personality: "品牌个性",
  visual_system: "视觉系统",
  creative_direction: "创意方向",
  primary_color: "主色",
  secondary_colors: "辅助色",
  typography: "字体建议",
  photography_style: "图片风格",
  logo_direction: "标志方向",
  image_rules: "图片规范",
  assets: "包装物料",
  asset_name: "物料名称",
  copy_text: "物料文案",
  channel: "使用渠道",
  image_brief: "画面简报",
  recommended_ratio: "建议比例",
  content_kit: "品牌文案包",
  brand_story: "品牌故事",
  store_bio: "店铺简介",
  selling_points: "核心卖点",
  tone_of_voice: "表达语气",
  reusable_headlines: "可复用标题",
  rollout_plan: "上线计划",
  task: "任务",
  deliverable: "交付物",
  priority: "优先级",
};

const OUTPUT_TITLES = {
  director: "创作方向说明",
  research: "受众洞察与内容策略",
  production: "完整制作方案",
  brand_packaging: "一站式包装方案",
  strategy: "内容策略方案",
  production_coordinator: "制作安排",
  copywriting: "完整文案",
  storyboard: "分镜脚本",
  video_prompt: "视频生成说明",
  reviewer: "交付前检查",
  video_generation: "视频生成结果",
};

export function buildTurnMarkdown(turn, project) {
  const title = OUTPUT_TITLES[turn.nodeName] || `${turn.meta.name} 的创作成果`;
  const lines = [
    `# ${title}`,
    "",
    `> ${turn.meta.completedTitle}。这份内容已经替你整理好，可以直接阅读，也可以提出想重做的地方。`,
    "",
  ];
  appendValue(lines, turn.output || { summary: turn.summary }, 2);
  appendFooter(lines, project?.title);
  return lines.join("\n").trim();
}

export function buildFinalMarkdown(result, project) {
  const title = result?.brand_packaging?.brand_foundation?.brand_name || result?.copywriting?.title || project?.title || "内容创作完整交付";
  const lines = [
    `# ${title}`,
    "",
    result?.brand_packaging
      ? "> 这份方案已经完成从定位、视觉、物料到上线计划的完整接力，可以直接作为品牌或店铺包装执行稿。"
      : "> 这份作品已经完成从方向、文案、分镜到生成说明的完整接力。愿它不只是一份交付，也能让你的下一步更有底气。",
    "",
  ];

  ["brand_packaging", "strategy", "copywriting", "storyboard", "video_prompt", "review", "video_task"].forEach((key) => {
    if (result?.[key]) {
      lines.push(`## ${SECTION_TITLES[key]}`, "");
      appendValue(lines, result[key], 3);
    }
  });
  appendFooter(lines, project?.title);
  return lines.join("\n").trim();
}

export function markdownFileName(title, fallback = "创作成果") {
  const safeTitle = String(title || fallback)
    .replace(/[\\/:*?"<>|#]/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 48);
  return `${safeTitle || fallback}.md`;
}

function appendValue(lines, value, depth, label) {
  if (isEmpty(value)) return;

  if (Array.isArray(value)) {
    value.forEach((item, index) => {
      if (isRecord(item)) {
        lines.push(`${"#".repeat(Math.min(depth, 4))} ${item.title || item.name || item.shot_id || `${label || "内容"} ${index + 1}`}`, "");
        appendValue(lines, item, depth + 1);
      } else {
        lines.push(`- ${formatScalar(item)}`);
      }
    });
    lines.push("");
    return;
  }

  if (isRecord(value)) {
    Object.entries(value).forEach(([key, item]) => {
      if (isEmpty(item) || ["workflow_type", "provider", "provider_parameters", "fact_bindings", "reference_ids", "allowed_reference_ids", "providers", "error_code", "error_message", "is_mock", "task_id"].includes(key)) return;
      const fieldLabel = FIELD_LABELS[key] || SECTION_TITLES[key] || humanizeKey(key);
      if (isRecord(item) || (Array.isArray(item) && item.some(isRecord))) {
        lines.push(`${"#".repeat(Math.min(depth, 4))} ${fieldLabel}`, "");
        appendValue(lines, item, depth + 1, fieldLabel);
      } else if (Array.isArray(item)) {
        lines.push(`**${fieldLabel}**`, "");
        appendValue(lines, item, depth + 1, fieldLabel);
      } else if (key === "result_url" && typeof item === "string") {
        lines.push(`**${fieldLabel}**：[打开视频](${item})`, "");
      } else if (key === "progress" && typeof item === "number") {
        lines.push(`**${fieldLabel}**：${Math.round(item * 100)}%`, "");
      } else if (typeof item === "string" && item.includes("\n")) {
        lines.push(`**${fieldLabel}**`, "", item, "");
      } else {
        lines.push(`**${fieldLabel}**：${formatScalar(item)}`, "");
      }
    });
    return;
  }

  lines.push(label ? `**${label}**：${formatScalar(value)}` : formatScalar(value), "");
}

function appendFooter(lines, projectTitle) {
  lines.push("---", "", `由创作 Agent 团队为你整理${projectTitle ? ` · ${projectTitle}` : ""}`);
}

function formatScalar(value) {
  if (typeof value === "boolean") return value ? "是" : "否";
  if (typeof value === "number" && value > 0 && value < 1) return `${Math.round(value * 100)}%`;
  const statusLabels = { completed: "已完成", pass: "已通过", failed: "未通过", running: "进行中", pending: "等待中" };
  if (statusLabels[value]) return statusLabels[value];
  return String(value).replace(/\s+/g, " ").trim();
}

function humanizeKey(key) {
  return key.split("_").filter(Boolean).map((part) => part.charAt(0).toUpperCase() + part.slice(1)).join(" ");
}

function isRecord(value) {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function isEmpty(value) {
  return value == null || value === "" || (Array.isArray(value) && value.length === 0) || (isRecord(value) && Object.keys(value).length === 0);
}
