const PURPOSE_LABELS = {
  hook: "钩子",
  selling_point: "卖点",
  proof: "证明",
  transition: "转场",
  cta: "行动号召",
  other: "其他",
};

export function StoryboardOutput({ output }) {
  return (
    <>
      <p className="output-lead">{output.visual_style}</p>
      <div className="storyboard-meta">
        <span>{output.total_duration_seconds} 秒</span>
        <span>{output.shots?.length || 0} 个镜头</span>
      </div>
      {output.continuity_rules?.length > 0 && (
        <section className="output-section">
          <h3>连续性规则</h3>
          <ul className="output-list">{output.continuity_rules.map((rule) => <li key={rule}>{rule}</li>)}</ul>
        </section>
      )}
      <div className="storyboard-shots">
        {(output.shots || []).map((shot) => (
          <article key={shot.shot_id}>
            <header>
              <span>镜头 {shot.order}</span>
              <time>{formatRange(shot.start_seconds, shot.end_seconds)}</time>
              <small>{PURPOSE_LABELS[shot.purpose] || shot.purpose}</small>
            </header>
            <h3>{shot.visual}</h3>
            <dl>
              <div><dt>主体</dt><dd>{shot.subject}</dd></div>
              <div><dt>动作</dt><dd>{shot.action}</dd></div>
              <div><dt>机位</dt><dd>{[shot.camera?.shot_size, shot.camera?.angle, shot.camera?.movement].filter(Boolean).join(" · ")}</dd></div>
              <div><dt>口播</dt><dd>{shot.voiceover || "—"}</dd></div>
              <div><dt>屏幕文字</dt><dd>{shot.onscreen_text || "—"}</dd></div>
              <div><dt>转场</dt><dd>{shot.transition || "—"}</dd></div>
            </dl>
            <div className="shot-prompt"><strong>生成提示词</strong><p>{shot.generation_prompt}</p></div>
          </article>
        ))}
      </div>
    </>
  );
}

function formatRange(start, end) {
  return `${Number(start).toFixed(1)}–${Number(end).toFixed(1)}s`;
}
