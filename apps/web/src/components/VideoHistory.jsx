const statusLabels = {
  draft: "待开始",
  running: "生成中",
  generating: "生成中",
  completed: "已完成",
  failed: "失败",
  cancelled: "已取消",
};

export function VideoHistory({ currentId, history, isLoading, onSelect }) {
  return (
    <aside className="video-history" aria-label="视频生成历史">
      <header>
        <p>生成记录</p>
        <span>{history.length ? `${history.length} 条` : "自动保存"}</span>
      </header>
      {isLoading && history.length === 0 ? (
        <div className="video-history-loading" aria-busy="true" aria-label="正在加载历史记录">
          <span /><span /><span />
        </div>
      ) : history.length === 0 ? (
        <div className="video-history-empty">
          <strong>还没有生成记录</strong>
          <p>第一条视频生成后会保存在这里。</p>
        </div>
      ) : (
        <ol>
          {history.map((item) => (
            <li key={item.id}>
              <button className={item.id === currentId ? "is-active" : ""} type="button" onClick={() => onSelect(item.id)}>
                <span className="video-history-copy">
                  <strong>{item.title}</strong>
                  <small>{formatTime(item.created_at)} · {statusLabels[item.status] || item.status}</small>
                </span>
              </button>
            </li>
          ))}
        </ol>
      )}
    </aside>
  );
}

function formatTime(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "刚刚";
  return new Intl.DateTimeFormat("zh-CN", {
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}
