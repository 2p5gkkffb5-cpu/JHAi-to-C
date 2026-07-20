export const AGENT_META = {
  intent_router: {
    name: "智能意图路由",
    activeTitle: "正在选择最合适的创作方式",
    completedTitle: "已经为你选好执行路径",
    thinking: "正在结合你的选择、描述和素材类型，判断要进入哪一条固定服务流程。",
    completed: "需求已经进入最匹配的固定流程。",
  },
  director: {
    name: "需求导演 Agent",
    activeTitle: "先把你的想法听明白",
    completedTitle: "你的创作方向已经被稳稳接住",
    thinking: "正在理解你真正想表达的重点，把模糊的想法整理成清楚的方向。",
    activeUpdates: [
      { title: "先把你的想法听明白", summary: "正在理解你真正想表达的重点，把模糊的想法整理成清楚的方向。" },
      { title: "正在提炼这次创作的核心目标", summary: "我们在确认内容要打动谁、解决什么问题，以及最终希望观众记住什么。" },
      { title: "正在把创作边界一项项理顺", summary: "平台、时长、语气和必须保留的信息正在汇成一份可执行的创意简报。" },
    ],
    completed: "目标、受众和创作边界已经理顺，后面的伙伴可以放心接力。",
    artifact: "creative_brief",
  },
  research: {
    name: "研究策略 Agent",
    activeTitle: "正在替你摸清值得走的方向",
    completedTitle: "有把握的创作方向已经浮现",
    thinking: "正在寻找受众真正关心的点，并比较哪条内容路径更容易被看见。",
    activeUpdates: [
      { title: "正在替你摸清值得走的方向", summary: "正在寻找受众真正关心的点，并比较哪条内容路径更容易被看见。" },
      { title: "正在核对和筛选相关资料", summary: "有价值的信息正在被留下，重复或缺少依据的内容会先排除。" },
      { title: "正在把洞察变成不同创意路线", summary: "我们在比较开场吸引力、品牌契合度和实际制作难度。" },
      { title: "正在收束更有胜算的推荐方向", summary: "几条策略正在做最后比较，很快会把更适合执行的一条交给制作伙伴。" },
    ],
    completed: "受众洞察和可执行方向已经整理好，你可以挑最心动的一条继续。",
    artifact: "research",
  },
  production: {
    name: "整合制作 Agent",
    activeTitle: "正在把好想法变成能落地的作品",
    completedTitle: "一套完整的制作方案已经成形",
    thinking: "正在把策略接成文案、分镜和视频指令，让灵感不只停留在纸面上。",
    activeUpdates: [
      { title: "正在把好想法变成能落地的作品", summary: "正在把策略拆成文案、分镜和视频指令，让灵感不只停留在纸面上。" },
      { title: "正在打磨开场、旁白和行动引导", summary: "表达节奏正在逐句调整，既要抓住注意力，也要让卖点自然落下来。" },
      { title: "正在安排镜头和画面节奏", summary: "每个镜头的作用、时长和衔接正在对齐，确保整条内容顺畅连贯。" },
      { title: "正在整理视频生成需要的完整指令", summary: "画面风格、主体动作和需要避免的问题正在汇总，很快就能交付完整方案。" },
    ],
    completed: "文案、镜头和生成指令已经彼此对齐，可以直接进入制作。",
    artifact: "video_prompt",
  },
  brand_packaging: {
    name: "一站式包装 Agent",
    activeTitle: "正在把零散素材包装成一个完整品牌",
    completedTitle: "一套可直接执行的包装方案已经成形",
    thinking: "正在统一品牌定位、视觉方向、店铺物料和销售文案。",
    activeUpdates: [
      { title: "正在读懂你提供的图片和基本信息", summary: "我们在提取真实可见的产品、风格和品牌线索。" },
      { title: "正在收束品牌定位与视觉语言", summary: "受众、核心价值、色彩与图片风格正在对齐。" },
      { title: "正在整理店铺和品牌所需物料", summary: "头像、店招、核心套图、详情模块与文案正在形成完整清单。" },
      { title: "正在安排上线顺序", summary: "包装物料和执行步骤正在做最后检查，很快就能交付。" },
    ],
    completed: "定位、视觉、物料、文案和上线计划已经彼此对齐。",
    artifact: "brand_packaging",
  },
  strategy: { name: "内容策划 Agent", activeTitle: "正在替你挑出更有胜算的表达", completedTitle: "更适合你的内容路径已经选好", thinking: "正在比较不同创意方向，兼顾吸引力、品牌感和落地难度。", completed: "策略已经收束成清晰选择，接下来每一步都会更笃定。", artifact: "strategy" },
  production_coordinator: { name: "制作统筹 Agent", activeTitle: "正在把复杂制作安排得井井有条", completedTitle: "制作节奏已经替你排好了", thinking: "正在拆开任务、确认素材边界，让后面的创作少走弯路。", completed: "任务和素材边界已经对齐，创作伙伴可以顺畅接棒。" },
  copywriting: { name: "营销文案 Agent", activeTitle: "正在替你的内容找到一句抓人的开场", completedTitle: "这段文案已经有了让人停下来的力量", thinking: "正在打磨开场、旁白和行动引导，让表达既自然又有记忆点。", completed: "开场、正文和行动引导已经连成一气，读起来更像一次真诚交流。", artifact: "copywriting" },
  storyboard: { name: "分镜设计 Agent", activeTitle: "正在把文字变成脑海里看得见的画面", completedTitle: "每一个镜头都已经找到自己的位置", thinking: "正在安排镜头、节奏和画面动作，让观众自然地一路看下去。", completed: "镜头节奏和视觉重点已经铺好，拍摄或生成时会更从容。", artifact: "storyboard" },
  video_prompt: { name: "视频提示词 Agent", activeTitle: "正在把画面愿望翻译成生成工具听得懂的话", completedTitle: "画面已经有了一份可靠的生成说明", thinking: "正在把分镜整理为清晰的视频指令，尽量减少生成结果跑偏。", completed: "画面风格、动作和限制已经说清楚，可以安心交给视频工具。", artifact: "video_prompt" },
  reviewer: { name: "质量守门 Agent", activeTitle: "正在替你做交付前的最后一遍把关", completedTitle: "作品已经经过一次认真体检", thinking: "正在检查事实、节奏和生成可行性，不让小问题消耗你的好创意。", completed: "关键细节已经检查完，能改的隐患都提前拦在了交付之前。", artifact: "review" },
  video_generation: {
    name: "视频生成 Agent",
    activeTitle: "正在把这一路的努力变成真正的画面",
    completedTitle: "你的作品已经从想法走到了成片",
    thinking: "正在提交视频任务并守着生成进度，离成片又近了一步。",
    activeUpdates: [
      { title: "正在把这一路的努力变成真正的画面", summary: "视频任务已经进入生成流程，我们会继续守着它的状态。" },
      { title: "画面正在生成，请再给它一点时间", summary: "生成工具正在处理镜头、动作和画面风格，这一步通常需要多等一会儿。" },
      { title: "还在认真生成，没有停住", summary: "任务仍在正常推进，我们正在等待生成工具返回最新结果。" },
      { title: "正在做成片交付前的最后等待", summary: "一旦视频生成完成，完整文档和成片入口会一起出现在这里。" },
    ],
    completed: "视频已经生成完成，这一路的创作接力有了可以看见的结果。",
  },
  image_generation: {
    name: "图片生成工具",
    activeTitle: "正在准备图片生成",
    completedTitle: "图片生成流程已经完成",
    thinking: "正在整理图片生成需要的输入。",
    completed: "图片生成流程已经结束。",
  },
};

const TOOL_LABELS = {
  research_search: "资料查找",
  structured_generation: "内容整理",
  video_generation: "视频生成",
};

export function deriveAgentTurns(project, events) {
  const turns = [];
  const attempts = new Map();

  events.forEach((event) => {
    const nodeName = event.node_name;
    if (!nodeName || !AGENT_META[nodeName]) return;

    if (event.event_type === "node.started") {
      const attempt = Number(event.payload?.attempt) || (attempts.get(nodeName) || 0) + 1;
      attempts.set(nodeName, attempt);
      turns.push({
        id: `${nodeName}-${event.id}`,
        taskId: event.payload?.task_id || "",
        nodeName,
        meta: AGENT_META[nodeName],
        attempt,
        provider: event.payload?.provider || "",
        tools: normalizeTools(event.payload?.tools, event.payload?.provider),
        startedAt: event.created_at,
        completedAt: null,
        status: "running",
        summary: "",
        output: null,
        trace: [],
        decision: null,
        decisionFeedback: "",
      });
      return;
    }

    if (event.event_type.startsWith("trace.")) {
      const turn = findTraceTurn(turns, nodeName, event)
        || createFallbackTurn(turns, nodeName, event, attempts);
      turn.trace.push({
        id: event.id,
        phase: event.payload?.phase || event.event_type.slice("trace.".length),
        summary: event.payload?.summary || "",
        status: event.payload?.status || "",
        createdAt: event.created_at,
      });
      return;
    }

    if (["node.completed", "node.failed"].includes(event.event_type)) {
      const turn = findLatestTurn(turns, nodeName) || createFallbackTurn(turns, nodeName, event, attempts);
      turn.status = event.event_type === "node.failed" ? "failed" : "completed";
      turn.completedAt = event.created_at;
      turn.duration = formatDuration(turn.startedAt, turn.completedAt, event.payload?.duration_ms);
      turn.hasEventSummary = Boolean(event.payload?.summary);
      turn.summary = event.payload?.summary || summarizeArtifact(project, nodeName);
      turn.output = normalizeOutput(event.payload?.output);
      turn.tools = mergeTools(
        turn.tools,
        normalizeTools(event.payload?.tools, event.payload?.provider),
      );
      return;
    }

    if (["agent.approved", "feedback.approved"].includes(event.event_type)
      || (event.event_type === "agent.decision_submitted" && event.payload?.action === "approve")) {
      const turn = findLatestTurn(turns, nodeName);
      if (turn) turn.decision = "approve";
    }
    if (["agent.retry_requested", "agent.retry_queued", "feedback.retry_requested", "retry.queued"].includes(event.event_type)
      || (event.event_type === "agent.decision_submitted" && event.payload?.action === "retry")) {
      const turn = findLatestTurn(turns, nodeName);
      if (turn) {
        turn.decision = "retry";
        turn.decisionFeedback = event.payload?.feedback || turn.decisionFeedback;
      }
    }
  });

  if (project?.current_node && AGENT_META[project.current_node] && !turns.length && project.status !== "draft") {
    createFallbackTurn(turns, project.current_node, {
      id: "current",
      created_at: project.updated_at,
      payload: {},
    }, attempts);
  }
  if (project?.status === "cancelled") {
    turns.forEach((turn) => {
      if (turn.status === "running") turn.status = "cancelled";
    });
  }
  hydrateLatestOutputs(turns, project);
  preserveHistoricalSummaries(turns);
  return turns;
}

function createFallbackTurn(turns, nodeName, event, attempts) {
  const turn = {
    id: `${nodeName}-${event.id}`,
    taskId: event.payload?.task_id || "",
    nodeName,
    meta: AGENT_META[nodeName],
    attempt: attempts.get(nodeName) || 1,
    provider: event.payload?.provider || "",
    tools: normalizeTools(event.payload?.tools, event.payload?.provider),
    startedAt: event.created_at,
    completedAt: null,
    status: "running",
    summary: "",
    output: null,
    trace: [],
    decision: null,
    decisionFeedback: "",
  };
  turns.push(turn);
  return turn;
}

function hydrateLatestOutputs(turns, project) {
  const artifactByNode = {
    director: "creative_brief",
    research: "research",
    strategy: "strategy",
    copywriting: "copywriting",
    storyboard: "storyboard",
    video_prompt: "video_prompt",
    reviewer: "review",
    brand_packaging: "brand_packaging",
  };
  const latestByNode = new Map();
  turns.forEach((turn, index) => latestByNode.set(turn.nodeName, index));
  turns.forEach((turn, index) => {
    if (turn.output || latestByNode.get(turn.nodeName) !== index) return;
    if (turn.nodeName === "research") {
      turn.output = normalizeOutput({
        research: project?.artifacts?.research,
        strategies: project?.artifacts?.strategy,
      });
      return;
    }
    if (turn.nodeName === "production") {
      turn.output = normalizeOutput({
        copywriting: project?.artifacts?.copywriting,
        storyboard: project?.artifacts?.storyboard,
        video_prompt: project?.artifacts?.video_prompt,
      });
      return;
    }
    const artifactName = artifactByNode[turn.nodeName];
    const fallback = turn.nodeName === "video_generation"
      ? project?.video_task
      : project?.artifacts?.[artifactName];
    turn.output = normalizeOutput(fallback);
  });
}

function normalizeOutput(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  return Object.keys(value).length ? value : null;
}

function findTraceTurn(turns, nodeName, event) {
  const taskId = event.payload?.task_id;
  if (taskId) {
    const matched = [...turns].reverse().find((turn) => turn.taskId === taskId);
    if (matched) return matched;
  }
  return findLatestTurn(turns, nodeName);
}

function findLatestTurn(turns, nodeName) {
  return [...turns].reverse().find((turn) => turn.nodeName === nodeName && turn.status === "running")
    || [...turns].reverse().find((turn) => turn.nodeName === nodeName);
}

function normalizeTools(tools, provider) {
  if (Array.isArray(tools)) {
    return tools.map((tool) => {
      const name = typeof tool === "string" ? tool : tool.display_name || tool.name;
      return TOOL_LABELS[name] || name;
    }).filter(Boolean);
  }
  return provider ? [`${provider} Provider`] : [];
}

function mergeTools(current, incoming) {
  return [...new Set([...current, ...incoming])];
}

function preserveHistoricalSummaries(turns) {
  const latestByNode = new Map();
  turns.forEach((turn, index) => latestByNode.set(turn.nodeName, index));
  turns.forEach((turn, index) => {
    if (turn.status === "completed" && !turn.hasEventSummary && latestByNode.get(turn.nodeName) !== index) {
      turn.summary = `${turn.meta.name} 本次结果已保留为历史版本。`;
    }
  });
}

function formatDuration(startedAt, completedAt, durationMs) {
  const milliseconds = Number(durationMs) || (new Date(completedAt).getTime() - new Date(startedAt).getTime());
  if (!Number.isFinite(milliseconds) || milliseconds < 0) return "";
  if (milliseconds < 1000) return `${milliseconds} ms`;
  return `${(milliseconds / 1000).toFixed(milliseconds < 10000 ? 1 : 0)} 秒`;
}

function summarizeArtifact(project, nodeName) {
  const artifactName = AGENT_META[nodeName]?.artifact;
  const artifact = artifactName ? project?.artifacts?.[artifactName] : null;
  if (!artifact) {
    if (nodeName === "video_generation" && project?.video_task) return `视频生成进度 ${Math.round((project.video_task.progress || 0) * 100)}%`;
    return "";
  }
  if (nodeName === "director") return artifact.content_direction || artifact.goal || "创作需求已完成拆解。";
  if (nodeName === "research") return artifact.suggestions?.[0] || artifact.audience_insights?.[0]?.claim || "研究与策略已整理。";
  if (nodeName === "production") return project?.artifacts?.copywriting?.title || "制作包已完成。";
  if (nodeName === "brand_packaging") return artifact.executive_summary || "一站式包装方案已完成。";
  if (nodeName === "strategy") {
    const option = artifact.strategy_options?.find((item) => item.strategy_id === artifact.recommended_strategy_id);
    return option ? `推荐「${option.name}」：${option.summary}` : artifact.recommendation_reason;
  }
  if (nodeName === "copywriting") return `${artifact.title}：${artifact.voiceover}`;
  if (nodeName === "storyboard") return `已完成 ${artifact.shots?.length || 0} 个镜头，视觉方向：${artifact.visual_style || "已确定"}`;
  if (nodeName === "video_prompt") return artifact.prompt;
  if (nodeName === "reviewer") return `质量评分 ${artifact.score} 分${artifact.required_changes?.length ? `，需调整：${artifact.required_changes.join("；")}` : "，审核通过"}`;
  return "";
}
