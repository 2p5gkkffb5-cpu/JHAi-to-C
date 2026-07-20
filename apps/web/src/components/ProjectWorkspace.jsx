import { useEffect, useMemo, useRef, useState } from "react";
import { AgentTurn } from "./AgentTurn.jsx";
import { ImageAttachmentPicker } from "./ImageAttachmentPicker.jsx";
import { buildFinalMarkdown, buildTurnMarkdown, markdownFileName } from "./agentMarkdown.js";
import { AGENT_META, deriveAgentTurns } from "./agentTimeline.js";
import { useRotatingValue } from "./useRotatingValue.js";
import { useImageAttachment } from "../hooks/useImageAttachment.js";

const ASSET = "/brand/";
const TERMINAL_STATUSES = new Set(["completed", "failed", "cancelled"]);
const ACTIVE_HEADER_MESSAGES = [
  "放心，我们正在一步步替你推进",
  "任务还在继续，新的进展正在路上",
  "这一棒正在认真处理，请再稍等一下",
];
const CREATION_MODES = [
  { label: "Agent 模式", value: "full_creation" },
  { label: "智能模式", value: "auto" },
  { label: "视频生成", value: "video_generation" },
  { label: "图片生成", value: "image_generation" },
  { label: "一站式包装", value: "brand_packaging" },
];

export function ProjectWorkspace({ workflow, onCreateProject, onReset = workflow.reset, scrollContainerRef }) {
  const { project, events, result, error, isDeciding, isCancelling, decideAgent, retry } = workflow;
  const feedEndRef = useRef(null);
  const shouldFollowRef = useRef(true);
  const autoApprovalRef = useRef("");
  const turns = useMemo(() => deriveAgentTurns(project, events), [project, events]);
  const latestTurn = turns[turns.length - 1];
  const isWaiting = project?.status === "waiting_approval" || project?.status === "waiting_strategy";
  const isFinalApproval = isWaiting && ["production", "brand_packaging"].includes(project.current_node);
  const isPackagingProject = project?.resolved_intent === "brand_packaging" || project?.requested_mode === "brand_packaging";
  const isActive = project && !TERMINAL_STATUSES.has(project.status);
  const { index: headerMessageIndex, value: activeHeaderMessage } = useRotatingValue(
    ACTIVE_HEADER_MESSAGES,
    {
      enabled: isActive && !isFinalApproval,
      intervalMs: 5200,
      resetKey: `${project?.id}:${project?.current_node}`,
    },
  );
  const approvalTurn = isFinalApproval
    ? [...turns].reverse().find((turn) => turn.nodeName === project.current_node && turn.status !== "running") || latestTurn
    : null;

  useEffect(() => {
    if (!isWaiting || isFinalApproval || isDeciding) return;
    const approvalKey = `${project.id}:${project.current_node}`;
    if (autoApprovalRef.current === approvalKey) return;
    autoApprovalRef.current = approvalKey;
    const strategyId = project.current_node === "research"
      ? project.artifacts?.strategy?.recommended_strategy_id || null
      : null;
    void decideAgent({
      action: "approve",
      feedback: "",
      nodeName: project.current_node,
      strategyId,
    }).catch(() => {
      autoApprovalRef.current = "";
    });
  }, [decideAgent, isDeciding, isFinalApproval, isWaiting, project]);

  useEffect(() => {
    const scrollContainer = scrollContainerRef?.current;
    if (!scrollContainer) return undefined;
    const updateFollowState = () => {
      shouldFollowRef.current = scrollContainer.scrollHeight - scrollContainer.scrollTop - scrollContainer.clientHeight < 200;
    };
    scrollContainer.addEventListener("scroll", updateFollowState, { passive: true });
    return () => scrollContainer.removeEventListener("scroll", updateFollowState);
  }, [scrollContainerRef]);

  useEffect(() => {
    shouldFollowRef.current = true;
  }, [project?.id]);

  useEffect(() => {
    if (!shouldFollowRef.current) return undefined;
    const frameId = window.requestAnimationFrame(() => {
      const scrollContainer = scrollContainerRef?.current;
      if (!feedEndRef.current || !scrollContainer) return;
      scrollContainer.scrollTo({
        top: scrollContainer.scrollHeight,
        behavior: events.length > 1 ? "smooth" : "auto",
      });
    });
    return () => window.cancelAnimationFrame(frameId);
  }, [events.length, isWaiting, project?.current_node, project?.id, project?.status, scrollContainerRef]);

  if (!project) {
    return (
      <section className="agent-thread agent-thread--empty" aria-label="新建 Agent 对话">
        <header className="thread-header">
          <h1>今天</h1>
        </header>
        <div className="agent-empty-state">
          <img src={`${ASSET}public-placeholder.svg`} alt="" />
          <h2>从一个想法开始</h2>
          <p>描述你想做的内容，Agent 会帮你拆解任务并推进创作。</p>
        </div>
        {error && (
          <div className="thread-error" role="alert">
            <span>{error.message}</span>
          </div>
        )}
        <FollowupComposer isWaiting={false} onCreateProject={onCreateProject} workflow={workflow} />
      </section>
    );
  }

  return (
    <section className="agent-thread" aria-label="Agent 执行过程">
      <header className="thread-header">
        <h1>今天</h1>
      </header>

      <div className="user-turn">
        <p>{project.request_text}</p>
        {project.references?.some((reference) => reference.type === "image") && (
          <div className="user-reference-images" aria-label="本次创作引用的图片">
            {project.references.filter((reference) => reference.type === "image").map((reference) => (
              <figure key={reference.id}>
                <img src={reference.snapshot?.url} alt={reference.label} />
                <figcaption>{reference.label.replace(/^@/, "")}</figcaption>
              </figure>
            ))}
          </div>
        )}
      </div>

      <div className="agent-response">
        <div className="response-heading">
          <span className={isActive && !isFinalApproval ? "turn-status-refresh" : undefined} key={isActive && !isFinalApproval ? headerMessageIndex : "settled"}>
            {isFinalApproval || TERMINAL_STATUSES.has(project.status) ? "这一路，已经替你推进到这里" : activeHeaderMessage}
          </span>
          <img src={`${ASSET}public-placeholder.svg`} alt="" />
        </div>

        <div className="agent-feed" aria-label="创作接力摘要">
          {turns.map((turn, index) => (
            <AgentTurn
              isAwaiting={isFinalApproval && turn.nodeName === project.current_node && index === turns.length - 1}
              key={turn.id}
              step={index + 1}
              turn={turn}
            />
          ))}

          {isActive && !isFinalApproval && latestTurn?.status !== "running" && (
            <ThinkingIndicator label={turns.length ? "正在准备下一位 Agent…" : "正在理解你的创作需求…"} />
          )}

          {isFinalApproval && approvalTurn && (
            <MarkdownDelivery
              fileName={markdownFileName(`${approvalTurn.meta.name}成果`)}
              markdown={buildTurnMarkdown(approvalTurn, project)}
              note="这份阶段成果已经整理成 Markdown，你可以直接往下读，也可以下载留存。"
            />
          )}

          {isFinalApproval && (
            <ApprovalPrompt
              isDeciding={isDeciding}
              isCancelling={isCancelling}
              isPackaging={isPackagingProject}
              nodeName={project.current_node}
              onDecide={decideAgent}
            />
          )}

          {error && (
            <div className="thread-error" role="alert">
              <span>{error.message}</span>
              <button onClick={retry} type="button">重新连接</button>
            </div>
          )}

          {project.status === "cancelled" && (
            <TerminalMessage onReset={onReset} title="已取消当前任务">
              已停止后续 Agent 和工具调用，已完成的内容仍保留在上方。
            </TerminalMessage>
          )}
          {project.status === "failed" && (
            <TerminalMessage onReset={onReset} title="任务执行中断">
              {project.errors?.[0]?.message || "本次执行没有完成，你可以新建任务后重试。"}
            </TerminalMessage>
          )}
          {project.status === "completed" && result && <FinalDelivery project={project} result={result} />}
          {project.status === "completed" && !result && !error && <ThinkingIndicator label="正在整理最终交付…" />}
          <div className="feed-end" ref={feedEndRef} aria-hidden="true" />
        </div>
      </div>

      {!isWaiting && <FollowupComposer isWaiting={false} onCreateProject={onCreateProject} workflow={workflow} />}
    </section>
  );
}

function ThinkingIndicator({ label }) {
  return (
    <div className="thinking-indicator" aria-live="polite" role="status">
      <span aria-hidden="true"><i /><i /><i /></span>
      <strong>{label}</strong>
    </div>
  );
}

function ApprovalPrompt({ isCancelling, isDeciding, isPackaging, nodeName, onDecide }) {
  const headingRef = useRef(null);
  const [feedback, setFeedback] = useState("");
  const [pendingAction, setPendingAction] = useState(null);
  const meta = AGENT_META[nodeName] || AGENT_META.director;

  useEffect(() => {
    setFeedback("");
    setPendingAction(null);
    headingRef.current?.focus({ preventScroll: true });
  }, [nodeName]);

  const submit = async (action) => {
    setPendingAction(action);
    try {
      await onDecide({
        action,
        feedback,
        nodeName,
        strategyId: null,
      });
    } finally {
      setPendingAction(null);
    }
  };

  return (
    <section className="approval-prompt" aria-labelledby="approval-title">
      <span>最终成果确认</span>
      <h2 id="approval-title" ref={headingRef} tabIndex="-1">完整方案符合你的期待吗？</h2>
      <p>{meta.name} 已经完成全部方案。{isPackaging ? "满意后将完成本次包装方案交付" : "满意后将直接生成视频"}，不满意也可以按你的意见重新打磨最终成果。</p>

      <label className="feedback-field">
        <span>修改意见（重新生成时使用）</span>
        <textarea autoComplete="off" name="agent-feedback" onChange={(event) => setFeedback(event.target.value)} placeholder="例如：卖点更聚焦，语气更克制一些…" rows="2" value={feedback} />
      </label>
      <div className="approval-actions" aria-busy={isDeciding}>
        <button className="approve-button" disabled={isCancelling || isDeciding} onClick={() => void submit("approve").catch(() => {})} type="button">
          {pendingAction === "approve" ? "正在继续…" : "满意，继续"}
        </button>
        <button disabled={isCancelling || isDeciding} onClick={() => void submit("retry").catch(() => {})} type="button">
          {pendingAction === "retry" ? "正在重做…" : "重新生成"}
        </button>
      </div>
    </section>
  );
}

function TerminalMessage({ children, onReset, title }) {
  return (
    <div className="terminal-message" role="status">
      <img src={`${ASSET}public-placeholder.svg`} alt="" />
      <div><h2>{title}</h2><p>{children}</p></div>
      <button onClick={onReset} type="button">新建任务</button>
    </div>
  );
}

function FinalDelivery({ project, result }) {
  const title = result?.brand_packaging?.brand_foundation?.brand_name || result?.copywriting?.title || "内容项目已完成";
  const markdown = buildFinalMarkdown(result, project);
  return (
    <section className="final-delivery">
      <p>{result?.brand_packaging ? "完成了。品牌定位、视觉系统、店铺物料和核心文案已经汇成一份完整包装方案。" : "完成了。一路接力的想法、文案和画面已经汇成一份完整文档，你随时可以带走。"}</p>
      <MarkdownDelivery
        fileName={markdownFileName(title)}
        markdown={markdown}
        note="这是为你整理好的最终 Markdown 文件，既能直接阅读，也方便继续修改和分享。"
        videoUrl={result?.video_task?.result_url}
      />
    </section>
  );
}

function MarkdownDelivery({ fileName, markdown, note, videoUrl }) {
  const href = `data:text/markdown;charset=utf-8,${encodeURIComponent(markdown)}`;
  return (
    <section className="markdown-delivery" aria-label={`${fileName} 文档`}>
      <header className="markdown-delivery__header">
        <span className="markdown-file-icon" aria-hidden="true">MD</span>
        <span>
          <strong>{fileName}</strong>
          <small>{note}</small>
        </span>
        <span className="markdown-delivery__actions">
          {videoUrl && <a href={videoUrl} rel="noreferrer" target="_blank">查看成片</a>}
          <a download={fileName} href={href}>下载文档</a>
        </span>
      </header>
      <article className="markdown-preview">
        <MarkdownPreview markdown={markdown} />
      </article>
    </section>
  );
}

function MarkdownPreview({ markdown }) {
  return markdown.split("\n").map((line, index) => {
    const key = `${index}-${line.slice(0, 12)}`;
    if (line.startsWith("### ")) return <h3 key={key}>{inlineMarkdown(line.slice(4))}</h3>;
    if (line.startsWith("## ")) return <h2 key={key}>{inlineMarkdown(line.slice(3))}</h2>;
    if (line.startsWith("# ")) return <h1 key={key}>{inlineMarkdown(line.slice(2))}</h1>;
    if (line.startsWith("> ")) return <blockquote key={key}>{inlineMarkdown(line.slice(2))}</blockquote>;
    if (line.startsWith("- ")) return <p className="markdown-list-item" key={key}><span aria-hidden="true">•</span>{inlineMarkdown(line.slice(2))}</p>;
    if (/^\d+\.\s/.test(line)) return <p className="markdown-list-item" key={key}>{inlineMarkdown(line)}</p>;
    if (line === "---") return <hr key={key} />;
    if (!line) return <span className="markdown-space" key={key} aria-hidden="true" />;
    return <p key={key}>{inlineMarkdown(line)}</p>;
  });
}

function inlineMarkdown(value) {
  const chunks = String(value).split(/(\*\*[^*]+\*\*|\[[^\]]+\]\([^)]+\))/g).filter(Boolean);
  return chunks.map((chunk, index) => {
    if (chunk.startsWith("**") && chunk.endsWith("**")) return <strong key={`${chunk}-${index}`}>{chunk.slice(2, -2)}</strong>;
    const link = chunk.match(/^\[([^\]]+)\]\(([^)]+)\)$/);
    if (link) return <a href={link[2]} key={`${chunk}-${index}`} rel="noreferrer" target="_blank">{link[1]}</a>;
    return chunk;
  });
}

function FollowupComposer({ isWaiting, onCreateProject, workflow }) {
  const [value, setValue] = useState("");
  const [mode, setMode] = useState(CREATION_MODES[0]);
  const [isModeMenuOpen, setIsModeMenuOpen] = useState(false);
  const imageAttachment = useImageAttachment();
  const modeWrapRef = useRef(null);
  const modeButtonRef = useRef(null);
  const isNewConversation = !workflow.project;
  const isTerminal = TERMINAL_STATUSES.has(workflow.project?.status);
  const canAttach = isNewConversation || isTerminal;
  const canSend = Boolean(value.trim())
    && (isNewConversation || isWaiting || isTerminal)
    && !workflow.isDeciding
    && !workflow.isCreating
    && !imageAttachment.isUploading
    && !imageAttachment.error
    && (mode.value !== "brand_packaging" || imageAttachment.references.length > 0);

  useEffect(() => {
    if (!isModeMenuOpen) return undefined;

    const closeOnOutsideClick = (event) => {
      if (!modeWrapRef.current?.contains(event.target)) setIsModeMenuOpen(false);
    };
    const closeOnEscape = (event) => {
      if (event.key !== "Escape") return;
      setIsModeMenuOpen(false);
      modeButtonRef.current?.focus();
    };

    document.addEventListener("pointerdown", closeOnOutsideClick);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("pointerdown", closeOnOutsideClick);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [isModeMenuOpen]);

  const submit = async () => {
    const prompt = value.trim();
    if (!canSend) return;
    if (isWaiting) {
      await workflow.decideAgent({ action: "retry", feedback: prompt, nodeName: workflow.project.current_node, strategyId: null });
    } else {
      const references = imageAttachment.references;
      if (mode.value === "image_generation") {
        await onCreateProject(prompt, mode.value, references);
      } else {
        await workflow.createAndStart(prompt, mode.value, references);
      }
      imageAttachment.clear();
    }
    setValue("");
  };

  return (
    <section className="followup-composer" aria-label="继续创作">
      <ImageAttachmentPicker
        attachments={imageAttachment.attachments}
        disabled={!canAttach}
        error={imageAttachment.error}
        onRemove={imageAttachment.remove}
        onRetry={imageAttachment.retry}
        onSelect={imageAttachment.select}
        variant="followup"
      />
      <textarea
        aria-label={mode.value === "brand_packaging" ? "填写品牌或店铺基本信息" : "输入后续创作要求"}
        value={value}
        onChange={(event) => setValue(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            void submit().catch(() => {});
          }
        }}
        placeholder={mode.value === "brand_packaging" ? "填写品牌/店铺名称、主营内容、目标人群和偏好风格…" : isNewConversation ? "描述你的创作需求，开始与 Agent 协作" : isWaiting ? "输入修改意见，重新生成当前步骤" : isTerminal ? "输入新的创作需求" : "Agent 正在工作，完成后可以继续输入"}
      />
      <div className="composer-tools">
        <div className="composer-mode-wrap" ref={modeWrapRef}>
          <button
            aria-controls={isModeMenuOpen ? "followup-creation-mode-menu" : undefined}
            aria-expanded={isModeMenuOpen}
            aria-haspopup="listbox"
            className={`composer-mode-trigger${mode.value === "full_creation" ? " is-agent" : ""}`}
            onClick={() => setIsModeMenuOpen((current) => !current)}
            onKeyDown={(event) => {
              if (event.key !== "ArrowDown") return;
              event.preventDefault();
              setIsModeMenuOpen(true);
            }}
            ref={modeButtonRef}
            type="button"
          >
            <img src={`${ASSET}public-placeholder.svg`} alt="" />
            {mode.label}
            <img className="composer-mode-chevron" src={`${ASSET}public-placeholder.svg`} alt="" />
          </button>
          {isModeMenuOpen && (
            <div className="composer-mode-menu" id="followup-creation-mode-menu" role="listbox" aria-label="生成模式">
              {CREATION_MODES.map((item) => (
                <button
                  aria-selected={item.value === mode.value}
                  className={item.value === mode.value ? "selected" : ""}
                  key={item.value}
                  onClick={() => {
                    setMode(item);
                    setIsModeMenuOpen(false);
                    modeButtonRef.current?.focus();
                  }}
                  role="option"
                  type="button"
                >
                  {item.label}
                </button>
              ))}
            </div>
          )}
        </div>
        <button type="button">自动</button>
        <button type="button">使用技能</button>
      </div>
      <button className="followup-send" disabled={!canSend} type="button" aria-label={workflow.isCreating ? "正在创建任务" : "发送"} onClick={() => void submit().catch(() => {})}>
        <img src={`${ASSET}public-placeholder.svg`} alt="" />
      </button>
      {imageAttachment.error && (
        <p className="followup-attachment-error" role="alert">{imageAttachment.error}</p>
      )}
      {mode.value === "brand_packaging" && imageAttachment.references.length === 0 && !imageAttachment.isUploading && (
        <p className="followup-attachment-error">一站式包装需要先上传参考图片</p>
      )}
    </section>
  );
}
