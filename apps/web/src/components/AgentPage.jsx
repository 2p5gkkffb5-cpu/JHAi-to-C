import { useRef, useState } from "react";
import { ProjectWorkspace } from "./ProjectWorkspace.jsx";

const ASSET = "/brand/";
const STATUS_LABELS = {
  completed: "已完成",
  cancelled: "已取消",
  failed: "生成失败",
  waiting_approval: "等待确认",
  waiting_strategy: "等待确认",
};

export function AgentPage({ onAction, onCreateProject, onNewConversation, onSelectProject = workflow.selectProject, workflow }) {
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const mainRef = useRef(null);
  const isActive = workflow.project && !["completed", "failed", "cancelled"].includes(workflow.project.status);

  return (
    <main className={`agent-page${isCollapsed ? " is-collapsed" : ""}`}>
      <aside className="agent-conversations" aria-label="Agent 会话">
        <header>
          <strong>开启创作</strong>
          <button
            className="conversation-collapse"
            type="button"
            aria-label={isCollapsed ? "展开会话栏" : "收起会话栏"}
            onClick={() => setIsCollapsed((value) => !value)}
          >
            <img src={`${ASSET}public-placeholder.svg`} alt="" />
          </button>
        </header>

        <button className="agent-new-chat" type="button" onClick={onNewConversation}>
          <img src={`${ASSET}public-placeholder.svg`} alt="" />
          <span>新对话</span>
        </button>

        <div className="agent-recent">
          <span>最近</span>
          {workflow.isLoadingProjects && workflow.projects.length === 0 && (
            <small className="agent-history-state" role="status">正在加载历史对话…</small>
          )}
          {workflow.projectsError && workflow.projects.length === 0 && (
            <button
              className="agent-history-state is-error"
              type="button"
              onClick={() => void workflow.refreshProjects()}
            >
              加载失败，点击重试
            </button>
          )}
          {!workflow.isLoadingProjects && !workflow.projectsError && workflow.projects.length === 0 && (
            <small className="agent-history-state">暂无历史对话</small>
          )}
          {workflow.projects.map((item) => (
            <button
              aria-current={item.id === workflow.projectId ? "page" : undefined}
              className={`agent-chat-item${item.id === workflow.projectId ? " is-active" : ""}`}
              key={item.id}
              type="button"
              onClick={() => onSelectProject(item.id)}
            >
              <img src={`${ASSET}public-placeholder.svg`} alt="" />
              <span>
                <strong>{item.title || item.request_text}</strong>
                <small>{STATUS_LABELS[item.status] || "Agent 创作中"}</small>
              </span>
            </button>
          ))}
        </div>
      </aside>

      <section className="agent-main" ref={mainRef}>
        <header className="agent-topbar">
          <button className="mobile-new-chat" type="button" onClick={onNewConversation}>
            <img src={`${ASSET}public-placeholder.svg`} alt="" />
            新对话
          </button>
          <div className="agent-topbar-actions">
            {isActive && (
              <button
                aria-busy={workflow.isCancelling}
                aria-label={workflow.isCancelling ? "正在取消当前任务" : "取消当前任务"}
                className="topbar-cancel"
                disabled={workflow.isCancelling || workflow.isDeciding}
                onClick={() => void workflow.cancel().catch(() => {})}
                type="button"
              >
                <span aria-hidden="true" className="cancel-stop-icon" />
                {workflow.isCancelling ? "正在取消" : "取消任务"}
              </button>
            )}
            {searchOpen ? (
              <label className="agent-search">
                <span className="visually-hidden">搜索当前会话</span>
                <input autoFocus onBlur={() => setSearchOpen(false)} placeholder="搜索当前会话" type="search" />
              </label>
            ) : (
              <button type="button" onClick={() => setSearchOpen(true)}>搜索</button>
            )}
            <FilterButton label="时间" />
            <FilterButton label="生成模式" />
            <FilterButton label="操作类型" />
            <button className="asset-library-button" type="button" onClick={() => onAction("资产库")}>
              <img src={`${ASSET}public-placeholder.svg`} alt="" />
              资产库
            </button>
          </div>
        </header>

        <div className="agent-canvas">
          <ProjectWorkspace
            workflow={workflow}
            onCreateProject={onCreateProject}
            onReset={onNewConversation}
            scrollContainerRef={mainRef}
          />
        </div>
      </section>
    </main>
  );
}

function FilterButton({ label }) {
  const [open, setOpen] = useState(false);
  return (
    <span className="filter-wrap">
      <button aria-expanded={open} aria-haspopup="menu" type="button" onClick={() => setOpen((value) => !value)}>
        {label}
        <img src={`${ASSET}public-placeholder.svg`} alt="" />
      </button>
      {open && (
        <span className="filter-menu" role="menu">
          <button role="menuitem" type="button" onClick={() => setOpen(false)}>全部</button>
          <button role="menuitem" type="button" onClick={() => setOpen(false)}>当前会话</button>
        </span>
      )}
    </span>
  );
}
