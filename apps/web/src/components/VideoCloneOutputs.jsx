const STAGES = [
  ["video_clone_analysis", "样片解析", "钩子、节奏与镜头 DNA"],
  ["video_clone_mapping", "素材映射", "逐镜头替换与合规改写"],
  ["video_clone_prompt", "提示词优化", "时间轴与生成约束"],
  ["video_clone_review", "成片验收", "结构匹配与生成质量"],
];

export function VideoCloneOutputs({ current }) {
  if (!current) return null;
  const artifacts = current.artifacts || {};
  return (
    <section className="video-clone-outputs" aria-label="视频复刻执行结果">
      <header>
        <div><p>PROCESS OUTPUT</p><h2>复刻执行单</h2></div>
        <span>{statusLabel(current.status)}</span>
      </header>
      <div className="video-clone-output-stages">
        {STAGES.map(([key, title, description], index) => {
          const output = artifacts[key];
          const active = current.current_node === key;
          const completed = Boolean(output);
          return (
            <article className={active ? "is-active" : completed ? "is-completed" : ""} key={key}>
              <div className="video-clone-output-stage-heading">
                <span>{String(index + 1).padStart(2, "0")}</span>
                <div><strong>{title}</strong><small>{description}</small></div>
                <em>{completed ? "已完成" : active ? "执行中" : "待执行"}</em>
              </div>
              {completed && <StageBody stage={key} output={output} />}
            </article>
          );
        })}
      </div>
    </section>
  );
}

function StageBody({ stage, output }) {
  if (stage === "video_clone_analysis") return <AnalysisBody output={output} />;
  if (stage === "video_clone_mapping") return <MappingBody output={output} />;
  if (stage === "video_clone_prompt") return <PromptBody output={output} />;
  return <ReviewBody output={output} />;
}

function AnalysisBody({ output }) {
  const technical = output.technical || {};
  return (
    <div className="video-clone-output-body">
      <dl>
        <Metric label="分析依据" value={analysisBasisLabel(output.analysis_basis)} />
        <Metric label="时长" value={technical.duration_seconds ? `${Number(technical.duration_seconds).toFixed(1)} 秒` : "—"} />
        <Metric label="尺寸" value={technical.width && technical.height ? `${technical.width} × ${technical.height}` : "—"} />
        <Metric label="镜头数" value={output.shots?.length || 0} />
      </dl>
      <p><strong>爆点：</strong>{output.hook_summary}</p>
      <p><strong>节奏：</strong>{output.pacing_summary}</p>
      <TagList items={output.transferable_dna} />
      <ShotList items={output.shots} render={(shot) => `${shot.start_seconds}–${shot.end_seconds}s · ${shot.reusable_pattern}`} />
    </div>
  );
}

function MappingBody({ output }) {
  return (
    <div className="video-clone-output-body">
      <p>{output.strategy}</p>
      <TagList items={output.continuity_rules} />
      <ShotList
        items={output.mappings}
        render={(item) => `${item.rewritten_subject} · ${item.rewritten_action}`}
      />
    </div>
  );
}

function PromptBody({ output }) {
  return (
    <div className="video-clone-output-body">
      <p>{output.optimization_summary}</p>
      <ShotList items={output.shot_prompts} render={(item) => item.prompt} />
      <details>
        <summary>查看最终生成提示词</summary>
        <pre>{output.generation?.prompt}</pre>
      </details>
    </div>
  );
}

function ReviewBody({ output }) {
  return (
    <div className="video-clone-output-body">
      <dl>
        <Metric label="验收结果" value={output.status === "pass" ? "通过" : output.status === "warning" ? "有提醒" : "未通过"} />
        <Metric label="评分" value={output.score} />
        <Metric label="复核依据" value={analysisBasisLabel(output.analysis_basis)} />
      </dl>
      <ShotList items={output.checks} render={(item) => `${item.status.toUpperCase()} · ${item.name} · ${item.evidence}`} />
      {output.repair_suggestions?.length > 0 && <TagList items={output.repair_suggestions} />}
    </div>
  );
}

function analysisBasisLabel(value) {
  if (value === "gemini_native_video") return "Gemini 原生视频 + 关键帧";
  if (value === "ffmpeg_keyframes") return "FFmpeg 关键帧";
  return "Mock 演示";
}

function Metric({ label, value }) {
  return <div><dt>{label}</dt><dd>{value}</dd></div>;
}

function TagList({ items = [] }) {
  if (!items.length) return null;
  return <ul className="video-clone-output-tags">{items.map((item) => <li key={item}>{item}</li>)}</ul>;
}

function ShotList({ items = [], render }) {
  if (!items.length) return null;
  return (
    <ol className="video-clone-output-list">
      {items.map((item, index) => (
        <li key={item.shot_id || item.name || index}>
          <span>{item.shot_id || String(index + 1).padStart(2, "0")}</span>
          <p>{render(item)}</p>
        </li>
      ))}
    </ol>
  );
}

function statusLabel(status) {
  return {
    draft: "等待开始",
    running: "解析中",
    generating: "生成中",
    reviewing: "验收中",
    completed: "已交付",
    failed: "执行失败",
    cancelled: "已取消",
  }[status] || status;
}
