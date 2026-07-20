import { StoryboardOutput } from "./StoryboardOutput.jsx";
import { StrategyOutput } from "./StrategyOutput.jsx";

const OUTPUT_TITLES = {
  intent_router: "智能路由结果",
  director: "创意简报",
  research: "研究结论与内容策略",
  production: "完整制作包",
  brand_packaging: "一站式包装方案",
  strategy: "内容策略方案",
  production_coordinator: "制作执行计划",
  copywriting: "完整文案",
  storyboard: "分镜脚本",
  video_prompt: "视频生成指令",
  reviewer: "质量审核报告",
  video_generation: "视频生成结果",
  image_generation: "图片生成结果",
};

export function AgentOutput({ agentName, nodeName, output, summary }) {
  return (
    <section className="agent-output" aria-label={`${agentName} 实际输出`}>
      <header className="agent-output__header">
        <span>实际输出</span>
        <h2>{OUTPUT_TITLES[nodeName] || `${agentName} 交付内容`}</h2>
      </header>
      <div className="agent-output__body">
        <OutputBody nodeName={nodeName} output={output} summary={summary} />
      </div>
    </section>
  );
}

function OutputBody({ nodeName, output, summary }) {
  if (!output) return <p className="output-summary">{summary}</p>;
  if (nodeName === "intent_router") return <IntentRouterOutput output={output} />;
  if (nodeName === "director") return <DirectorOutput output={output} />;
  if (nodeName === "research") return <ResearchStrategyOutput output={output} />;
  if (nodeName === "production") return <ProductionOutput output={output} />;
  if (nodeName === "brand_packaging") return <BrandPackagingOutput output={output} />;
  if (nodeName === "strategy") return <StrategyOutput output={output} />;
  if (nodeName === "production_coordinator") return <CoordinatorOutput output={output} />;
  if (nodeName === "copywriting") return <CopywritingOutput output={output} />;
  if (nodeName === "storyboard") return <StoryboardOutput output={output} />;
  if (nodeName === "video_prompt") return <VideoPromptOutput output={output} />;
  if (nodeName === "reviewer") return <ReviewOutput output={output} />;
  if (nodeName === "video_generation") return <VideoGenerationOutput output={output} />;
  return <p className="output-summary">{summary}</p>;
}

function BrandPackagingOutput({ output }) {
  const foundation = output.brand_foundation || {};
  const visual = output.visual_system || {};
  return (
    <>
      <p className="output-lead">{output.executive_summary}</p>
      <FactGrid items={[
        ["包装类型", output.package_type === "store" ? "店铺包装" : "品牌包装"],
        ["品牌名称", foundation.brand_name],
        ["品牌定位", foundation.positioning],
        ["目标人群", foundation.target_audience],
        ["核心价值", foundation.value_proposition],
        ["品牌口号", foundation.slogan],
      ]} />
      <OutputSection title="品牌个性" when={Boolean(foundation.personality?.length)}><TagList items={foundation.personality} /></OutputSection>
      <OutputSection title="视觉系统">
        <p className="output-script">{visual.creative_direction}</p>
        <FactGrid items={[["主色", visual.primary_color], ["字体", visual.typography], ["图片风格", visual.photography_style], ["标志方向", visual.logo_direction]]} />
        <TagList items={visual.secondary_colors} />
        <BulletList items={visual.image_rules} />
      </OutputSection>
      <OutputSection title="包装物料" when={Boolean(output.assets?.length)}>
        <div className="output-packaging-assets">
          {(output.assets || []).map((asset) => (
            <article key={`${asset.channel}-${asset.asset_name}`}>
              <header><strong>{asset.asset_name}</strong><span>{asset.channel} · {asset.recommended_ratio}</span></header>
              <p>{asset.copy_text}</p>
              <small>{asset.purpose}｜{asset.image_brief}</small>
            </article>
          ))}
        </div>
      </OutputSection>
      <OutputSection title="品牌文案包" when={Boolean(output.content_kit)}>
        <p className="output-script">{output.content_kit?.brand_story}</p>
        <FactGrid items={[["店铺简介", output.content_kit?.store_bio]]} />
        <TagList items={output.content_kit?.selling_points} />
        <BulletList items={output.content_kit?.reusable_headlines} />
      </OutputSection>
      <OutputSection title="上线计划" when={Boolean(output.rollout_plan?.length)}>
        <ol className="output-rollout">
          {(output.rollout_plan || []).map((step) => (
            <li key={step.order}><strong>{step.task}</strong><span>{step.deliverable} · {step.priority}</span></li>
          ))}
        </ol>
      </OutputSection>
      <OutputSection title="执行假设" when={Boolean(output.assumptions?.length)}><BulletList items={output.assumptions} /></OutputSection>
    </>
  );
}

function IntentRouterOutput({ output }) {
  const labels = {
    full_creation: "完整 Agent 创作",
    video_generation: "直接视频生成",
    image_generation: "图片生成",
    brand_packaging: "一站式包装服务",
  };
  return (
    <FactGrid items={[
      ["已识别模式", labels[output.intent] || output.intent],
      ["判断置信度", Number.isFinite(Number(output.confidence)) ? `${Math.round(Number(output.confidence) * 100)}%` : null],
    ]} />
  );
}

function ResearchStrategyOutput({ output }) {
  const research = output.research || output;
  return <><ResearchOutput output={research} />{output.strategies && <StrategyOutput output={output.strategies} />}</>;
}

function ProductionOutput({ output }) {
  return (
    <>
      {output.production_plan && <CoordinatorOutput output={output.production_plan} />}
      {output.copywriting && <CopywritingOutput output={output.copywriting} />}
      {output.storyboard && <StoryboardOutput output={output.storyboard} />}
      {output.video_prompt && <VideoPromptOutput output={output.video_prompt} />}
    </>
  );
}

function DirectorOutput({ output }) {
  const brief = output.creative_brief || output;
  return (
    <>
      <p className="output-lead">{brief.content_direction}</p>
      <FactGrid items={[
        ["产品", brief.product],
        ["行业", brief.industry],
        ["目标", brief.goal],
        ["目标受众", brief.target_audience],
        ["平台", brief.platform],
        ["规格", brief.duration_seconds && `${brief.duration_seconds} 秒 · ${brief.aspect_ratio}`],
      ]} />
      <OutputSection title="内容语气" when={Boolean(brief.tone?.length)}><TagList items={brief.tone} /></OutputSection>
      <OutputSection title="必须包含" when={Boolean(brief.must_include?.length)}><BulletList items={brief.must_include} /></OutputSection>
      <OutputSection title="需要避免" when={Boolean(brief.must_avoid?.length)}><BulletList items={brief.must_avoid} /></OutputSection>
      <OutputSection title="执行假设" when={Boolean(output.assumptions?.length)}><BulletList items={output.assumptions} /></OutputSection>
      <OutputSection title="待补充信息" when={Boolean(output.missing_fields?.length)}><BulletList items={output.missing_fields} /></OutputSection>
    </>
  );
}

function ResearchOutput({ output }) {
  return (
    <>
      <OutputSection title="受众洞察" when={Boolean(output.audience_insights?.length)}>
        <div className="output-insights">
          {(output.audience_insights || []).map((insight, index) => (
            <article key={`${insight.claim}-${index}`}>
              <p>{insight.claim}</p>
              <small>置信度 {Math.round((insight.confidence || 0) * 100)}% · {evidenceLabel(insight.evidence_type)}</small>
            </article>
          ))}
        </div>
      </OutputSection>
      <OutputSection title="竞品常用路径" when={Boolean(output.competitor_patterns?.length)}><BulletList items={output.competitor_patterns} /></OutputSection>
      <OutputSection title="内容趋势" when={Boolean(output.content_trends?.length)}><TagList items={output.content_trends} /></OutputSection>
      <OutputSection title="执行建议" when={Boolean(output.suggestions?.length)}><BulletList items={output.suggestions} ordered /></OutputSection>
      <OutputSection title="风险提示" when={Boolean(output.risk_notes?.length)}><BulletList items={output.risk_notes} /></OutputSection>
      <OutputSection title="研究来源" when={Boolean(output.sources?.length)}>
        <div className="output-sources">
          {(output.sources || []).map((source) => (
            <article key={source.source_id}>
              <strong>{source.title}</strong>
              <p>{source.summary}</p>
              <small>{evidenceLabel(source.evidence_type)}</small>
              {source.url && <a href={source.url} rel="noreferrer" target="_blank">查看来源</a>}
            </article>
          ))}
        </div>
      </OutputSection>
    </>
  );
}

function CoordinatorOutput({ output }) {
  return (
    <>
      <p className="output-lead">{output.production_goal}</p>
      <FactGrid items={[
        ["文案要求", output.copywriting_instruction],
        ["分镜要求", output.storyboard_instruction],
        ["视频指令要求", output.video_prompt_instruction],
      ]} />
      <OutputSection title="连续性规则" when={Boolean(output.continuity_rules?.length)}><BulletList items={output.continuity_rules} /></OutputSection>
      <OutputSection title="允许使用的引用" when={Boolean(output.allowed_reference_ids?.length)}><TagList items={output.allowed_reference_ids} /></OutputSection>
    </>
  );
}

function CopywritingOutput({ output }) {
  return (
    <>
      <h3 className="output-title">{output.title}</h3>
      <FactGrid items={[["开场钩子", output.hook], ["语气", output.tone], ["预计时长", output.estimated_duration_seconds && `${output.estimated_duration_seconds} 秒`]]} />
      <OutputSection title="完整口播"><p className="output-script">{output.voiceover}</p></OutputSection>
      <OutputSection title="屏幕文字" when={Boolean(output.onscreen_text?.length)}>
        <ol className="output-timeline">
          {(output.onscreen_text || []).map((item, index) => (
            <li key={`${item.start_seconds}-${index}`}><time>{formatRange(item.start_seconds, item.end_seconds)}</time><span>{item.text}</span></li>
          ))}
        </ol>
      </OutputSection>
      <OutputSection title="行动号召"><p className="output-script">{output.cta}</p></OutputSection>
      <OutputSection title="事实绑定" when={Boolean(output.fact_bindings?.length)}><TagList items={(output.fact_bindings || []).map((item) => `${item.field} ← ${item.reference_id}`)} /></OutputSection>
    </>
  );
}

function VideoPromptOutput({ output }) {
  const parameters = Object.entries(output.provider_parameters || {}).map(([key, value]) => `${key}: ${value}`);
  return (
    <>
      <FactGrid items={[["规格", output.duration_seconds && `${output.duration_seconds} 秒 · ${output.aspect_ratio}`]]} />
      <OutputSection title="正向提示词"><p className="output-prompt">{output.prompt}</p></OutputSection>
      <OutputSection title="负向提示词" when={Boolean(output.negative_prompt)}><p className="output-prompt is-negative">{output.negative_prompt}</p></OutputSection>
      <OutputSection title="引用素材" when={Boolean(output.reference_ids?.length)}><TagList items={output.reference_ids} /></OutputSection>
      <OutputSection title="生成参数" when={Boolean(parameters.length)}><TagList items={parameters} /></OutputSection>
    </>
  );
}

function ReviewOutput({ output }) {
  const passed = output.status === "pass";
  return (
    <>
      <div className={`review-score ${passed ? "is-pass" : "is-fail"}`}>
        <strong>{output.score}</strong><span>分 · {passed ? "审核通过" : "需要修改"}</span>
      </div>
      <OutputSection title="发现的问题" when={Boolean(output.issues?.length)}>
        <div className="output-issues">
          {(output.issues || []).map((issue) => (
            <article key={issue.issue_id}>
              <strong>{issue.category} · {issue.severity}</strong>
              <p>{issue.message}</p>
              {issue.suggested_fix && <small>建议：{issue.suggested_fix}</small>}
            </article>
          ))}
        </div>
      </OutputSection>
      <OutputSection title="必须调整" when={Boolean(output.required_changes?.length)}><BulletList items={output.required_changes} /></OutputSection>
      {output.return_to && <p className="output-note">需要返回：{output.return_to}</p>}
    </>
  );
}

function VideoGenerationOutput({ output }) {
  const progress = Number.isFinite(Number(output.progress)) ? `${Math.round(Number(output.progress) * 100)}%` : "—";
  return (
    <>
      <FactGrid items={[["状态", output.status], ["生成进度", progress], ["服务商", output.provider], ["任务 ID", output.task_id]]} />
      {output.result_url && <a className="output-result-link" href={output.result_url} rel="noreferrer" target="_blank">打开生成视频</a>}
      {output.error_message && <p className="output-note is-error">{output.error_message}</p>}
    </>
  );
}

function FactGrid({ items }) {
  const visibleItems = items.filter(([, value]) => value !== undefined && value !== null && value !== "");
  if (!visibleItems.length) return null;
  return <dl className="output-facts">{visibleItems.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{String(value)}</dd></div>)}</dl>;
}

function OutputSection({ children, title, when = true }) {
  if (!when) return null;
  return <section className="output-section"><h3>{title}</h3>{children}</section>;
}

function BulletList({ items = [], ordered = false }) {
  if (!items.length) return null;
  const Tag = ordered ? "ol" : "ul";
  return <Tag className={`output-list${ordered ? " is-ordered" : ""}`}>{items.map((item, index) => <li key={`${String(item)}-${index}`}>{String(item)}</li>)}</Tag>;
}

function TagList({ items = [] }) {
  if (!items.length) return null;
  return <div className="output-tags">{items.map((item, index) => <span key={`${String(item)}-${index}`}>{String(item)}</span>)}</div>;
}

function evidenceLabel(value) {
  return { user_input: "用户输入", brand_fact: "品牌资料", demo_source: "演示数据", external_source: "外部来源", inference: "推断" }[value] || value || "未标注";
}

function formatRange(start, end) {
  return `${Number(start).toFixed(1)}–${Number(end).toFixed(1)}s`;
}
