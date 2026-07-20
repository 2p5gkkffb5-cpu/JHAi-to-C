import { useRotatingValue } from "./useRotatingValue.js";
import { AgentRoleIcon } from "./AgentRoleIcon.jsx";

export function AgentTurn({ turn, isAwaiting, step }) {
  const isRunning = turn.status === "running";
  const activeUpdates = turn.meta.activeUpdates || [{
    title: turn.meta.activeTitle,
    summary: turn.meta.thinking,
  }];
  const { index: activeUpdateIndex, value: activeUpdate } = useRotatingValue(
    activeUpdates,
    { enabled: isRunning, resetKey: `${turn.id}:${turn.status}` },
  );
  const settledCopy = getSettledCopy(turn);
  const title = isRunning ? activeUpdate.title : settledCopy.title;
  const summary = shortenSummary(isRunning ? activeUpdate.summary : settledCopy.summary);

  return (
    <article className={`agent-turn is-${turn.status}${isAwaiting ? " is-awaiting" : ""}`}>
      <span className={`turn-state-icon is-${turn.nodeName}`} aria-hidden="true">
        <AgentRoleIcon nodeName={turn.nodeName} />
      </span>
      <div className="turn-summary">
        <span className="turn-step">第 {step} 步 · 调用了 {turn.meta.name}</span>
        <h2 className={isRunning ? "turn-status-refresh" : undefined} key={isRunning ? `title-${activeUpdateIndex}` : "title"}>
          {title}
        </h2>
        <p className={isRunning ? "turn-status-refresh" : undefined} key={isRunning ? `summary-${activeUpdateIndex}` : "summary"} aria-live={isRunning ? "polite" : undefined}>{summary}</p>
        {turn.tools.length > 0 && (
          <p className="turn-tools">
            <span aria-hidden="true">✦</span>
            这一步借助了 {turn.tools.join("、")}，帮你把费时间的部分先处理好。
          </p>
        )}
        {turn.attempt > 1 && <small>这是按你的想法重新打磨的第 {turn.attempt} 版。</small>}
        {turn.decision === "approve" && <small>你已经点头，我们继续把下一步接稳。</small>}
        {turn.decision === "retry" && (
          <small>已收到重做意见，这一版也为你保留着{turn.decisionFeedback ? `：${turn.decisionFeedback}` : "。"}</small>
        )}
      </div>
    </article>
  );
}

function getSettledCopy(turn) {
  if (turn.status === "failed") {
    return {
      title: "这一步需要缓一缓",
      summary: "这一棒遇到了一点阻碍，已停在这里等你决定。",
    };
  }
  if (turn.status === "cancelled") {
    return {
      title: "这一步已停止",
      summary: "当前任务已取消，这一步不会再继续执行。",
    };
  }
  return {
    title: turn.meta.completedTitle,
    summary: isTechnicalSummary(turn.summary) ? turn.meta.completed : turn.summary || turn.meta.completed,
  };
}

function shortenSummary(value) {
  if (!value) return "正在把零散的信息收拢成一份清楚、可继续推进的结果。";
  const text = String(value).replace(/\s+/g, " ").trim();
  return text.length > 112 ? `${text.slice(0, 112)}…` : text;
}

function isTechnicalSummary(value) {
  return /调用|provider|tool|结构化|执行当前|node|workflow/i.test(String(value || ""));
}
