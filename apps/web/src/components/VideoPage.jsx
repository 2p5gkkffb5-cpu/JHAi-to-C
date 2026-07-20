import { useEffect, useMemo, useRef, useState } from "react";
import { useVideoGenerations } from "../hooks/useVideoGenerations.js";
import { useVideoMaterials } from "../hooks/useVideoMaterials.js";
import { VideoHistory } from "./VideoHistory.jsx";
import { VideoMaterialPicker } from "./VideoMaterialPicker.jsx";
import {
  clearVideoDraft,
  createVideoDraftSignature,
  readVideoDraft,
  saveVideoDraft,
} from "./videoDraft.js";

const ASSET = "/brand/";
const ratios = ["9:16", "16:9", "1:1"];
const durations = [5, 10, 15];
const ACTIVE_STATUSES = new Set(["draft", "running", "generating", "reviewing"]);

export function VideoPage({
  enabled,
  ownerId,
  initialPrompt = "",
  initialReferences = [],
  onInitialInputConsumed,
}) {
  const restoredDraft = useMemo(
    () => initialPrompt || initialReferences.length ? null : readVideoDraft(ownerId),
    [initialPrompt, initialReferences, ownerId],
  );
  const startingReferences = initialReferences.length ? initialReferences : restoredDraft?.references || [];
  const [prompt, setPrompt] = useState(initialPrompt || restoredDraft?.prompt || "");
  const [aspectRatio, setAspectRatio] = useState(restoredDraft?.aspectRatio || "9:16");
  const [durationSeconds, setDurationSeconds] = useState(restoredDraft?.durationSeconds || 10);
  const [localError, setLocalError] = useState("");
  const [mention, setMention] = useState(null);
  const [saveState, setSaveState] = useState(restoredDraft ? "saved" : "idle");
  const [lastSavedAt, setLastSavedAt] = useState(restoredDraft?.savedAt || "");
  const textareaRef = useRef(null);
  const lastSavedSignature = useRef(restoredDraft ? createVideoDraftSignature(restoredDraft) : "");
  const materials = useVideoMaterials(startingReferences);
  const generations = useVideoGenerations({ enabled });
  const uploadedReferences = useMemo(
    () => materials.items.flatMap((item) => item.uploaded?.reference ? [item.uploaded.reference] : []),
    [materials.items],
  );
  const draft = useMemo(() => ({
    version: 1,
    prompt,
    aspectRatio,
    durationSeconds,
    references: uploadedReferences,
  }), [aspectRatio, durationSeconds, prompt, uploadedReferences]);
  const draftSignature = useMemo(() => createVideoDraftSignature(draft), [draft]);
  const mentionOptions = useMemo(() => {
    if (!mention) return [];
    const query = mention.query.toLocaleLowerCase();
    return materials.items.filter((item) => {
      const filename = item.uploaded?.filename || item.file?.name || "";
      return item.status === "uploaded" && filename.toLocaleLowerCase().includes(query);
    });
  }, [materials.items, mention]);

  useEffect(() => {
    if (initialPrompt || initialReferences.length) onInitialInputConsumed?.();
  }, [initialPrompt, initialReferences.length, onInitialInputConsumed]);

  useEffect(() => {
    if (lastSavedSignature.current && draftSignature === lastSavedSignature.current) {
      setSaveState("saved");
      return;
    }
    setSaveState(prompt.trim() || materials.items.length ? "dirty" : "idle");
  }, [draftSignature, materials.items.length, prompt]);

  const updateMention = (value, cursor) => {
    const beforeCursor = value.slice(0, cursor);
    const match = beforeCursor.match(/(?:^|\s)@([^\s@]*)$/u);
    setMention(match ? { start: cursor - match[1].length - 1, end: cursor, query: match[1] } : null);
  };

  const insertMention = (filename) => {
    const textarea = textareaRef.current;
    const selectionStart = textarea?.selectionStart ?? prompt.length;
    const activeMention = mention || { start: selectionStart, end: selectionStart };
    const prefix = activeMention.start === selectionStart
      && selectionStart > 0
      && !/\s/u.test(prompt[selectionStart - 1])
      ? " "
      : "";
    const token = `${prefix}@${filename} `;
    const nextPrompt = `${prompt.slice(0, activeMention.start)}${token}${prompt.slice(activeMention.end)}`;
    const nextCursor = activeMention.start + token.length;
    setPrompt(nextPrompt);
    setMention(null);
    window.requestAnimationFrame(() => {
      textarea?.focus();
      textarea?.setSelectionRange(nextCursor, nextCursor);
    });
  };

  const submit = async (event) => {
    event?.preventDefault();
    const cleanPrompt = prompt.trim();
    if (!cleanPrompt || generations.isCreating || materials.isUploading) return;
    setLocalError("");
    const references = materials.items.flatMap((item) => {
      const filename = item.uploaded?.filename;
      const reference = item.uploaded?.reference;
      return filename && reference && cleanPrompt.includes(`@${filename}`) ? [reference] : [];
    });
    try {
      await generations.generate({ prompt: cleanPrompt, references, durationSeconds, aspectRatio });
    } catch {
      // The hook exposes a stable error message and keeps the prompt for retry.
    }
  };

  const handleKeyDown = (event) => {
    if (event.key === "Escape" && mention) {
      event.preventDefault();
      setMention(null);
      return;
    }
    if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
      event.preventDefault();
      void submit();
    }
  };

  const handleNewTask = () => {
    clearVideoDraft(ownerId);
    generations.beginNewTask();
    materials.reset();
    setPrompt("");
    setAspectRatio("9:16");
    setDurationSeconds(10);
    setLocalError("");
    setMention(null);
    setSaveState("idle");
    setLastSavedAt("");
    lastSavedSignature.current = "";
    window.requestAnimationFrame(() => textareaRef.current?.focus());
  };

  const handleSaveDraft = () => {
    if (materials.isUploading) {
      setLocalError("素材上传完成后再保存草稿");
      return;
    }
    setLocalError("");
    try {
      const savedDraft = saveVideoDraft(ownerId, draft);
      lastSavedSignature.current = createVideoDraftSignature(savedDraft);
      setLastSavedAt(savedDraft.savedAt);
      setSaveState("saved");
    } catch (caught) {
      setLocalError(caught.message || "草稿保存失败，请检查浏览器存储权限");
    }
  };

  const error = localError || materials.error || generations.error;
  const isActive = ACTIVE_STATUSES.has(generations.current?.status);

  return (
    <main className="video-page">
      <div className="video-workspace">
        <header className="video-heading">
          <div>
            <p>AI 视频</p>
            <h1>让素材成为下一条片子</h1>
            <span>上传参考素材，用 @ 精确告诉模型该看什么。</span>
          </div>
          <div className="video-heading-actions">
            <span className="video-model-badge">Seedance · 智能生成</span>
            <button className="video-new-task" type="button" onClick={handleNewTask} disabled={generations.isCreating || isActive}>
              <span aria-hidden="true">＋</span>
              新建任务
            </button>
          </div>
        </header>

        <div className="video-layout">
          <VideoHistory
            currentId={generations.current?.id}
            history={generations.history}
            isLoading={generations.isLoading}
            onSelect={generations.select}
          />

          <section className="video-studio" aria-label="AI 视频生成工作台">
            <VideoPreview current={generations.current} isLoading={generations.isLoading} />

            <form className="video-composer" onSubmit={submit}>
              <VideoMaterialPicker
                items={materials.items}
                onAdd={materials.addFiles}
                onInsert={insertMention}
                onRemove={materials.remove}
              />

              <div className="video-prompt-field">
                <label htmlFor="video-prompt">视频描述</label>
                <span>{prompt.length}/5000</span>
                <div className="video-textarea-wrap">
                  <textarea
                    ref={textareaRef}
                    id="video-prompt"
                    maxLength={5000}
                    value={prompt}
                    onChange={(event) => {
                      setPrompt(event.target.value);
                      updateMention(event.target.value, event.target.selectionStart);
                    }}
                    onClick={(event) => updateMention(event.currentTarget.value, event.currentTarget.selectionStart)}
                    onKeyDown={handleKeyDown}
                    placeholder="例如：@产品正面.png 放在木桌中央，镜头缓慢环绕，午后自然光，质感真实"
                    aria-describedby="video-prompt-help"
                  />
                  {mention && (
                    <div className="video-mention-menu" role="listbox" aria-label="选择引用素材">
                      {mentionOptions.length ? mentionOptions.map((item) => {
                        const filename = item.uploaded.filename;
                        return (
                          <button type="button" role="option" aria-selected="false" key={item.localId} onClick={() => insertMention(filename)}>
                            {item.isVideo ? <video src={item.previewUrl} muted /> : <img src={item.previewUrl} alt="" />}
                            <span><strong>@{filename}</strong><small>{item.isVideo ? "视频素材" : "图片素材"}</small></span>
                          </button>
                        );
                      }) : <p>{materials.items.length ? "没有匹配的素材" : "请先上传素材"}</p>}
                    </div>
                  )}
                </div>
                <small id="video-prompt-help">输入 @ 或点击上方素材即可插入引用；未被 @ 的素材不会提交。</small>
              </div>

              <div className="video-options-row">
                <fieldset>
                  <legend>画面比例</legend>
                  <div>
                    {ratios.map((ratio) => (
                      <label className={aspectRatio === ratio ? "is-selected" : ""} key={ratio}>
                        <input type="radio" name="video-ratio" checked={aspectRatio === ratio} onChange={() => setAspectRatio(ratio)} />
                        {ratio}
                      </label>
                    ))}
                  </div>
                </fieldset>
                <label className="video-duration">
                  <span>时长</span>
                  <select value={durationSeconds} onChange={(event) => setDurationSeconds(Number(event.target.value))}>
                    {durations.map((duration) => <option value={duration} key={duration}>{duration} 秒</option>)}
                  </select>
                </label>
              </div>

              {error && <p className="video-error" role="alert">{error}</p>}
              <div className="video-submit-row">
                <span className="video-save-note" aria-live="polite">
                  {saveState === "saved" ? `草稿已保存${formatSavedTime(lastSavedAt)}` : "保存后刷新页面也不会丢失"}
                </span>
                <button
                  className={`video-save${saveState === "saved" ? " is-saved" : ""}`}
                  type="button"
                  onClick={handleSaveDraft}
                  disabled={materials.isUploading || saveState === "saved"}
                >
                  <span aria-hidden="true">{saveState === "saved" ? "✓" : "↓"}</span>
                  {saveState === "saved" ? "已保存" : saveState === "dirty" ? "保存更改" : "保存草稿"}
                </button>
                {isActive && <button className="video-cancel" type="button" onClick={() => void generations.cancel()}>取消本次生成</button>}
                <button className="video-generate" type="submit" disabled={!prompt.trim() || generations.isCreating || materials.isUploading || isActive}>
                  {generations.isCreating || isActive ? <span className="video-button-spinner" /> : <img src={`${ASSET}public-placeholder.svg`} alt="" />}
                  {generations.isCreating ? "正在创建" : isActive ? "正在生成" : "生成视频"}
                </button>
              </div>
            </form>
          </section>
        </div>
      </div>
    </main>
  );
}

function formatSavedTime(value) {
  const date = new Date(value);
  if (!value || Number.isNaN(date.getTime())) return "";
  return ` · ${new Intl.DateTimeFormat("zh-CN", { hour: "2-digit", minute: "2-digit" }).format(date)}`;
}

export function VideoPreview({ current, isLoading }) {
  const task = current?.video_task;
  if (isLoading && !current) {
    return <section className="video-preview is-loading" aria-busy="true"><div /><p>正在读取生成记录…</p></section>;
  }
  if (!current) {
    return (
      <section className="video-preview is-empty">
        <div className="video-preview-icon"><img src={`${ASSET}public-placeholder.svg`} alt="" /></div>
        <h2>视频会在这里生成</h2>
        <p>先添加素材和描述。每次生成都会自动进入左侧历史。</p>
      </section>
    );
  }
  if (current.status === "failed") {
    return <section className="video-preview is-error"><h2>这次生成没有完成</h2><p>{current.errors?.[0]?.message || task?.error_message || "请调整描述后重新生成。"}</p></section>;
  }
  if (current.status === "cancelled") {
    return <section className="video-preview is-empty"><h2>生成已取消</h2><p>记录已保留，你可以修改描述后再次生成。</p></section>;
  }
  if (current.status === "completed" && task?.result_url && !task.is_mock) {
    return (
      <section className="video-preview has-result">
        <video src={task.result_url} controls playsInline preload="metadata" />
        <div><span>生成完成</span><a href={task.result_url} target="_blank" rel="noreferrer" download>下载视频</a></div>
      </section>
    );
  }
  if (current.status === "completed") {
    return (
      <section className="video-preview is-mock-complete">
        <div className="video-mock-frame"><span>预览</span></div>
        <div><strong>生成完成</strong><span>当前使用演示视频服务，生成记录已完整保存。</span></div>
      </section>
    );
  }
  return (
    <section className="video-preview is-generating" aria-live="polite" aria-busy="true">
      <div className="video-generating-frame"><span /></div>
      <div><strong>正在生成视频</strong><span>{task?.progress ? `已处理 ${Math.round(task.progress * 100)}%` : "正在理解素材与镜头描述"}</span></div>
    </section>
  );
}
