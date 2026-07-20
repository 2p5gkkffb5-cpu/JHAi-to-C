import { useCallback, useEffect, useRef, useState } from "react";
import { uploadImage } from "../api/assets.js";

const MAX_IMAGE_BYTES = 10 * 1024 * 1024;
export const MAX_IMAGE_COUNT = 20;
const ALLOWED_IMAGE_TYPES = new Set(["image/jpeg", "image/png", "image/webp"]);

function attachmentId() {
  return globalThis.crypto?.randomUUID?.() || `image-${Date.now()}-${Math.random()}`;
}

export function useImageAttachment() {
  const [attachments, setAttachments] = useState([]);
  const [validationError, setValidationError] = useState("");
  const attachmentsRef = useRef([]);
  const uploadControllersRef = useRef(new Map());

  const commitAttachments = useCallback((nextAttachments) => {
    attachmentsRef.current = nextAttachments;
    setAttachments(nextAttachments);
  }, []);

  const updateAttachment = useCallback((id, update) => {
    const nextAttachments = attachmentsRef.current.map((attachment) => (
      attachment.id === id ? update(attachment) : attachment
    ));
    commitAttachments(nextAttachments);
  }, [commitAttachments]);

  const upload = useCallback(async (attachment) => {
    uploadControllersRef.current.get(attachment.id)?.abort();
    const controller = new AbortController();
    uploadControllersRef.current.set(attachment.id, controller);

    try {
      const uploaded = await uploadImage(attachment.file, controller.signal);
      if (controller.signal.aborted) return;
      updateAttachment(attachment.id, (current) => ({
        ...current,
        status: "uploaded",
        uploaded,
        error: "",
      }));
    } catch (error) {
      if (controller.signal.aborted) return;
      updateAttachment(attachment.id, (current) => ({
        ...current,
        status: "error",
        error: error instanceof Error ? error.message : "图片上传失败，请稍后重试",
      }));
    } finally {
      if (uploadControllersRef.current.get(attachment.id) === controller) {
        uploadControllersRef.current.delete(attachment.id);
      }
    }
  }, [updateAttachment]);

  const clear = useCallback(() => {
    uploadControllersRef.current.forEach((controller) => controller.abort());
    uploadControllersRef.current.clear();
    attachmentsRef.current.forEach((attachment) => URL.revokeObjectURL(attachment.previewUrl));
    commitAttachments([]);
    setValidationError("");
  }, [commitAttachments]);

  const remove = useCallback((id) => {
    uploadControllersRef.current.get(id)?.abort();
    uploadControllersRef.current.delete(id);
    const removed = attachmentsRef.current.find((attachment) => attachment.id === id);
    if (removed) URL.revokeObjectURL(removed.previewUrl);
    commitAttachments(attachmentsRef.current.filter((attachment) => attachment.id !== id));
    setValidationError("");
  }, [commitAttachments]);

  const select = useCallback(async (files) => {
    const selectedFiles = Array.from(files || []);
    if (selectedFiles.length === 0) return;

    const remainingSlots = MAX_IMAGE_COUNT - attachmentsRef.current.length;
    const errors = [];
    const validFiles = [];

    selectedFiles.slice(0, Math.max(remainingSlots, 0)).forEach((file) => {
      if (!ALLOWED_IMAGE_TYPES.has(file.type)) {
        errors.push(`${file.name} 不是支持的图片格式`);
      } else if (file.size > MAX_IMAGE_BYTES) {
        errors.push(`${file.name} 超过 10MB`);
      } else {
        validFiles.push(file);
      }
    });

    if (selectedFiles.length > remainingSlots) {
      errors.push(`最多可添加 ${MAX_IMAGE_COUNT} 张图片`);
    }
    setValidationError(errors[0] || "");
    if (validFiles.length === 0) return;

    const pendingAttachments = validFiles.map((file) => ({
      id: attachmentId(),
      file,
      previewUrl: URL.createObjectURL(file),
      status: "uploading",
      uploaded: null,
      error: "",
    }));
    commitAttachments([...attachmentsRef.current, ...pendingAttachments]);
    await Promise.all(pendingAttachments.map(upload));
  }, [commitAttachments, upload]);

  const retry = useCallback((id) => {
    const attachment = attachmentsRef.current.find((item) => item.id === id);
    if (!attachment) return;
    setValidationError("");
    const pending = { ...attachment, status: "uploading", error: "" };
    updateAttachment(id, () => pending);
    void upload(pending);
  }, [updateAttachment, upload]);

  useEffect(() => () => {
    uploadControllersRef.current.forEach((controller) => controller.abort());
    attachmentsRef.current.forEach((attachment) => URL.revokeObjectURL(attachment.previewUrl));
  }, []);

  const attachmentError = attachments.find((attachment) => attachment.error)?.error || "";

  return {
    attachments,
    clear,
    error: validationError || attachmentError,
    isUploading: attachments.some((attachment) => attachment.status === "uploading"),
    references: attachments
      .filter((attachment) => attachment.status === "uploaded")
      .map((attachment) => attachment.uploaded.reference),
    remove,
    retry,
    select,
  };
}
