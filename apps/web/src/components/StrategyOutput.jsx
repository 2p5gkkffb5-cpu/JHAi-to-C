const SCORE_LABELS = {
  brand_fit: "品牌匹配",
  conversion_fit: "转化潜力",
  execution_feasibility: "执行可行性",
  differentiation: "差异化",
};

export function StrategyOutput({ output }) {
  return (
    <>
      <p className="output-lead">推荐理由：{output.recommendation_reason}</p>
      <div className="strategy-output-list">
        {(output.strategy_options || []).map((option) => {
          const isRecommended = option.strategy_id === output.recommended_strategy_id;
          return (
            <article className={isRecommended ? "is-recommended" : ""} key={option.strategy_id}>
              <header>
                <div><h3>{option.name}</h3><p>{option.summary}</p></div>
                {isRecommended && <span>推荐</span>}
              </header>
              <dl className="strategy-output-details">
                <div><dt>目标受众</dt><dd>{option.target_audience}</dd></div>
                <div><dt>核心信息</dt><dd>{option.core_message}</dd></div>
                <div><dt>开场钩子</dt><dd>{option.hook}</dd></div>
                <div><dt>视觉方向</dt><dd>{option.visual_direction}</dd></div>
                <div><dt>行动号召</dt><dd>{option.cta}</dd></div>
              </dl>
              <LabeledItems label="卖点" items={option.selling_points} />
              <LabeledItems label="叙事结构" items={option.narrative_structure} ordered />
              <LabeledItems label="风险" items={option.risks} />
              <div className="strategy-scores">
                {Object.entries(option.scores || {}).map(([key, value]) => (
                  <span key={key}><b>{value}</b><small>{SCORE_LABELS[key] || key}</small></span>
                ))}
              </div>
            </article>
          );
        })}
      </div>
    </>
  );
}

function LabeledItems({ items = [], label, ordered = false }) {
  if (!items.length) return null;
  const Tag = ordered ? "ol" : "ul";
  return (
    <section className="strategy-items">
      <strong>{label}</strong>
      <Tag>{items.map((item, index) => <li key={`${item}-${index}`}>{item}</li>)}</Tag>
    </section>
  );
}
