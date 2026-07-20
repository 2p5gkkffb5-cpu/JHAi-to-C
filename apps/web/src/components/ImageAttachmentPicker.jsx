import { useLayoutEffect, useRef, useState } from "react";
import { MAX_IMAGE_COUNT } from "../hooks/useImageAttachment.js";

const ASSET = "/brand/";
const ATTACHMENT_CARD_WIDTH = 48;
const ATTACHMENT_ADD_SPACE = 36;
const ATTACHMENT_MAX_FAN_STEP = 44;
const ATTACHMENT_MAX_FAN_SPAN = 420;
const ATTACHMENT_EDGE_GAP = 16;
const ATTACHMENT_MIN_FAN_WIDTH = ATTACHMENT_CARD_WIDTH + ATTACHMENT_ADD_SPACE;
const ATTACHMENT_MAX_FAN_WIDTH = ATTACHMENT_MIN_FAN_WIDTH + ATTACHMENT_MAX_FAN_SPAN;

export function calculateAttachmentFanLayout(count, availableWidth = ATTACHMENT_MAX_FAN_WIDTH) {
  if (count <= 1) return { step: 0, width: 78 };
  const boundedWidth = Math.max(
    ATTACHMENT_MIN_FAN_WIDTH,
    Math.min(ATTACHMENT_MAX_FAN_WIDTH, availableWidth),
  );
  const step = Math.min(
    ATTACHMENT_MAX_FAN_STEP,
    Math.max(0, (boundedWidth - ATTACHMENT_MIN_FAN_WIDTH) / (count - 1)),
  );
  return {
    step,
    width: Math.min(boundedWidth, ATTACHMENT_MIN_FAN_WIDTH + step * (count - 1)),
  };
}

export function ImageAttachmentPicker({
  attachments = [],
  disabled = false,
  error = "",
  onRemove,
  onRetry,
  onSelect,
  variant = "home",
}) {
  const pickerRef = useRef(null);
  const inputRef = useRef(null);
  const dragDepthRef = useRef(0);
  const [isDragging, setIsDragging] = useState(false);
  const [availableFanWidth, setAvailableFanWidth] = useState(ATTACHMENT_MAX_FAN_WIDTH);
  const canAdd = !disabled && attachments.length < MAX_IMAGE_COUNT;
  const uploadedCount = attachments.filter((attachment) => attachment.status === "uploaded").length;
  const uploadingCount = attachments.filter((attachment) => attachment.status === "uploading").length;
  const failedCount = attachments.filter((attachment) => attachment.status === "error").length;
  const listState = attachments.length === 0 ? "is-empty" : attachments.length === 1 ? "is-single" : "is-multiple";
  const { step: fanStep, width: fanWidth } = calculateAttachmentFanLayout(
    attachments.length,
    availableFanWidth,
  );
  const addLabel = disabled
    ? "当前步骤不能新增参考图片"
    : attachments.length >= MAX_IMAGE_COUNT
      ? `最多可添加 ${MAX_IMAGE_COUNT} 张参考图片`
      : "添加参考图片（支持多选）";

  useLayoutEffect(() => {
    const picker = pickerRef.current;
    const container = picker?.parentElement;
    if (!picker || !container) return undefined;

    const updateAvailableWidth = () => {
      const containerWidth = container.getBoundingClientRect().width || container.clientWidth;
      if (!containerWidth) return;
      setAvailableFanWidth(Math.max(
        ATTACHMENT_MIN_FAN_WIDTH,
        containerWidth - picker.offsetLeft - ATTACHMENT_EDGE_GAP,
      ));
    };
    updateAvailableWidth();

    if (typeof ResizeObserver === "function") {
      const observer = new ResizeObserver(updateAvailableWidth);
      observer.observe(container);
      return () => observer.disconnect();
    }
    window.addEventListener("resize", updateAvailableWidth);
    return () => window.removeEventListener("resize", updateAvailableWidth);
  }, [variant]);

  const resetDragState = () => {
    dragDepthRef.current = 0;
    setIsDragging(false);
  };

  const handleDragEnter = (event) => {
    if (!canAdd || !event.dataTransfer?.types?.includes("Files")) return;
    event.preventDefault();
    dragDepthRef.current += 1;
    setIsDragging(true);
  };

  const handleDragLeave = (event) => {
    if (!isDragging) return;
    event.preventDefault();
    dragDepthRef.current = Math.max(0, dragDepthRef.current - 1);
    if (dragDepthRef.current === 0) setIsDragging(false);
  };

  const handleDrop = (event) => {
    if (!event.dataTransfer?.types?.includes("Files")) return;
    event.preventDefault();
    if (!canAdd) {
      resetDragState();
      return;
    }
    const files = Array.from(event.dataTransfer?.files || []);
    resetDragState();
    if (files.length) void onSelect(files);
  };

  return (
    <div
      ref={pickerRef}
      className={`image-attachment-picker is-${variant}${isDragging ? " is-dragging" : ""}`}
      onDragEnter={handleDragEnter}
      onDragLeave={handleDragLeave}
      onDragOver={(event) => {
        if (!event.dataTransfer?.types?.includes("Files")) return;
        event.preventDefault();
        event.dataTransfer.dropEffect = canAdd ? "copy" : "none";
      }}
      onDrop={handleDrop}
      style={{
        "--attachment-card-width": `${ATTACHMENT_CARD_WIDTH}px`,
        "--attachment-fan-step": `${fanStep}px`,
        "--attachment-fan-width": `${fanWidth}px`,
      }}
    >
      <div
        className={`attachment-list ${listState}`}
        aria-label="参考图片"
        role="list"
      >
        {attachments.map((attachment, index) => (
          <div
            className="attachment-item"
            key={attachment.id}
            role="listitem"
            style={{ "--attachment-index": index }}
          >
            <div className={`reference-card has-image is-${attachment.status}`}>
              <img className="attachment-preview" src={attachment.previewUrl} alt={`参考图片：${attachment.file.name}`} />
              {attachment.status === "uploading" && <span className="attachment-spinner" aria-hidden="true" />}
              {attachment.status === "error" && (
                <button
                  aria-label={`重新上传 ${attachment.file.name}`}
                  className="attachment-retry"
                  onClick={() => onRetry(attachment.id)}
                  title="上传失败，点击重试"
                  type="button"
                >!</button>
              )}
            </div>
            <button
              aria-label={`移除 ${attachment.file.name}`}
              className="attachment-remove"
              onClick={() => onRemove(attachment.id)}
              type="button"
            ><img src={`${ASSET}public-placeholder.svg`} alt="" /></button>
          </div>
        ))}
        {attachments.length < MAX_IMAGE_COUNT && (
          <button
            aria-label={addLabel}
            className="reference-card attachment-add"
            disabled={!canAdd}
            onClick={() => inputRef.current?.click()}
            title={addLabel}
            type="button"
          >
            <img src={`${ASSET}public-placeholder.svg`} alt="" />
            {attachments.length > 0 && <span aria-hidden="true">+</span>}
          </button>
        )}
      </div>
      <input
        ref={inputRef}
        className="visually-hidden"
        hidden
        type="file"
        accept="image/jpeg,image/png,image/webp,.jpg,.jpeg,.png,.webp"
        disabled={disabled}
        multiple
        onChange={(event) => {
          const files = Array.from(event.target.files || []);
          event.target.value = "";
          if (files.length) void onSelect(files);
        }}
      />
      {(attachments.length > 0 || error) && (
        <span className={`attachment-status${error || failedCount ? " is-error" : ""}`} role={error ? "alert" : "status"}>
          {error || (failedCount ? `${failedCount} 张上传失败` : uploadingCount ? `正在上传 ${uploadingCount} 张` : `已引用 ${uploadedCount} 张`)}
        </span>
      )}
      {isDragging && <span className="attachment-drop-hint" role="status">释放即可添加</span>}
    </div>
  );
}
