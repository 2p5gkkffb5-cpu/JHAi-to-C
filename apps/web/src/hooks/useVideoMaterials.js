import { useCallback, useEffect, useRef, useState } from "react";
import { uploadMaterial } from "../api/assets.js";

const MAX_ITEMS = 10;
const MAX_IMAGE_BYTES = 10 * 1024 * 1024;
const MAX_VIDEO_BYTES = 100 * 1024 * 1024;
const ALLOWED_TYPES = new Set([
  "image/jpeg",
  "image/png",
  "image/webp",
  "video/mp4",
  "video/quicktime",
  "video/webm",
]);

export function useVideoMaterials(initialReferences = []) {
  const [items, setItems] = useState(() => initialReferences.map(fromReference));
  const [error, setError] = useState("");
  const controllers = useRef(new Map());
  const itemsRef = useRef(items);
  itemsRef.current = items;

  const addFiles = useCallback(async (files) => {
    setError("");
    const available = MAX_ITEMS - itemsRef.current.length;
    const selected = [...files].slice(0, available);
    if (files.length > available) setError(`最多添加 ${MAX_ITEMS} 个素材`);

    for (const file of selected) {
      if (!ALLOWED_TYPES.has(file.type)) {
        setError("仅支持 JPEG、PNG、WebP、MP4、MOV 或 WebM 素材");
        continue;
      }
      const isVideo = file.type.startsWith("video/");
      const maxBytes = isVideo ? MAX_VIDEO_BYTES : MAX_IMAGE_BYTES;
      if (file.size > maxBytes) {
        setError(`${isVideo ? "视频" : "图片"}不能超过 ${maxBytes / 1024 / 1024}MB`);
        continue;
      }

      const localId = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
      const previewUrl = URL.createObjectURL(file);
      const pending = { localId, file, previewUrl, isVideo, isLocal: true, status: "uploading", uploaded: null, error: "" };
      setItems((current) => [...current, pending]);
      const controller = new AbortController();
      controllers.current.set(localId, controller);
      try {
        const uploaded = await uploadMaterial(file, controller.signal);
        setItems((current) => current.map((item) => item.localId === localId
          ? { ...item, status: "uploaded", uploaded }
          : item));
      } catch (caught) {
        if (!controller.signal.aborted) {
          setItems((current) => current.map((item) => item.localId === localId
            ? { ...item, status: "error", error: caught.message || "素材上传失败" }
            : item));
        }
      } finally {
        controllers.current.delete(localId);
      }
    }
  }, []);

  const remove = useCallback((localId) => {
    controllers.current.get(localId)?.abort();
    controllers.current.delete(localId);
    setItems((current) => {
      const target = current.find((item) => item.localId === localId);
      if (target?.previewUrl && target.isLocal) URL.revokeObjectURL(target.previewUrl);
      return current.filter((item) => item.localId !== localId);
    });
  }, []);

  const reset = useCallback(() => {
    controllers.current.forEach((controller) => controller.abort());
    controllers.current.clear();
    itemsRef.current.forEach((item) => {
      if (item.previewUrl && item.isLocal) URL.revokeObjectURL(item.previewUrl);
    });
    setItems([]);
    setError("");
  }, []);

  useEffect(() => () => {
    controllers.current.forEach((controller) => controller.abort());
    itemsRef.current.forEach((item) => {
      if (item.previewUrl && item.isLocal) URL.revokeObjectURL(item.previewUrl);
    });
  }, []);

  return {
    addFiles,
    error,
    isUploading: items.some((item) => item.status === "uploading"),
    items,
    references: items.flatMap((item) => item.uploaded?.reference ? [item.uploaded.reference] : []),
    remove,
    reset,
  };
}

function fromReference(reference, index) {
  const contentType = reference.snapshot?.content_type || "";
  return {
    localId: `initial-${reference.id}-${index}`,
    file: null,
    previewUrl: reference.snapshot?.url || "",
    isVideo: reference.type === "reference_video" || contentType.startsWith("video/"),
    isLocal: false,
    status: "uploaded",
    uploaded: {
      filename: reference.snapshot?.filename || reference.label?.replace(/^@/, "") || "素材",
      reference,
    },
    error: "",
  };
}
