import { useCallback, useEffect, useRef, useState } from "react";
import {
  cancelProject,
  createProject,
  getProject,
  listProjects,
  startProject,
  subscribeProjectEvents,
} from "../api/contentProjects.js";

const TERMINAL = new Set(["completed", "failed", "cancelled"]);

export function useVideoGenerations({ enabled, origin = "ai_video", requestedMode = "video_generation" }) {
  const [history, setHistory] = useState([]);
  const [current, setCurrent] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [error, setError] = useState("");
  const createController = useRef(null);
  const selectController = useRef(null);
  const operationVersion = useRef(0);
  const currentId = useRef(null);
  currentId.current = current?.id || null;

  const refresh = useCallback(async (signal) => {
    if (!enabled) return;
    const refreshVersion = operationVersion.current;
    setIsLoading(true);
    try {
      const videos = await listProjects(signal, origin);
      if (signal?.aborted || refreshVersion !== operationVersion.current) return;
      setHistory(videos);
      setError("");
      if (!currentId.current && videos[0]) {
        const project = await getProject(videos[0].id, signal);
        if (signal?.aborted || refreshVersion !== operationVersion.current) return;
        setCurrent(project);
      }
    } catch (caught) {
      if (!signal?.aborted && refreshVersion === operationVersion.current) {
        setError(caught.message || "暂时无法读取生成历史");
      }
    } finally {
      if (!signal?.aborted && refreshVersion === operationVersion.current) {
        setIsLoading(false);
      }
    }
  }, [enabled, origin]);

  useEffect(() => {
    if (!enabled) {
      setHistory([]);
      setCurrent(null);
      return undefined;
    }
    const controller = new AbortController();
    void refresh(controller.signal);
    return () => controller.abort();
  }, [enabled, refresh]);

  useEffect(() => {
    if (!enabled || !current?.id || TERMINAL.has(current.status)) return undefined;
    return subscribeProjectEvents(current.id, {
      onProject: (project) => {
        setCurrent(project);
        setHistory((items) => upsert(items, project));
      },
      onUnsupported: () => {
        const controller = new AbortController();
        const timer = window.setInterval(async () => {
          try {
            const project = await getProject(current.id, controller.signal);
            setCurrent(project);
            setHistory((items) => upsert(items, project));
            if (TERMINAL.has(project.status)) window.clearInterval(timer);
          } catch {
            window.clearInterval(timer);
          }
        }, 1500);
      },
    });
  }, [current?.id, current?.status, enabled]);

  useEffect(() => () => {
    createController.current?.abort();
    selectController.current?.abort();
  }, []);

  const generate = useCallback(async ({ prompt, references, durationSeconds, aspectRatio, targetPlatform = "douyin" }) => {
    operationVersion.current += 1;
    setIsLoading(false);
    createController.current?.abort();
    const controller = new AbortController();
    createController.current = controller;
    setIsCreating(true);
    setError("");
    try {
      const title = prompt.length > 60 ? `${prompt.slice(0, 60)}…` : prompt;
      const project = await createProject({
        title,
        request_text: prompt,
        references,
        blueprint_id: null,
        target_platform: targetPlatform,
        duration_seconds: durationSeconds,
        aspect_ratio: aspectRatio,
        requested_mode: requestedMode,
        origin,
      }, controller.signal);
      await startProject(project.id, controller.signal);
      setCurrent(project);
      setHistory((items) => upsert(items, project));
      return project;
    } catch (caught) {
      if (!controller.signal.aborted) setError(caught.message || "视频生成任务创建失败");
      throw caught;
    } finally {
      if (createController.current === controller) {
        createController.current = null;
        setIsCreating(false);
      }
    }
  }, [origin, requestedMode]);

  const select = useCallback(async (projectId) => {
    operationVersion.current += 1;
    selectController.current?.abort();
    const controller = new AbortController();
    selectController.current = controller;
    setIsLoading(true);
    setError("");
    try {
      const project = await getProject(projectId, controller.signal);
      if (selectController.current === controller && !controller.signal.aborted) {
        setCurrent(project);
      }
    } catch (caught) {
      if (!controller.signal.aborted) setError(caught.message || "暂时无法读取这条记录");
    } finally {
      if (selectController.current === controller) {
        selectController.current = null;
        setIsLoading(false);
      }
    }
  }, []);

  const cancel = useCallback(async () => {
    if (!current || TERMINAL.has(current.status)) return;
    const targetId = current.id;
    setError("");
    try {
      await cancelProject(targetId);
      setCurrent((project) => project?.id === targetId
        ? { ...project, status: "cancelled" }
        : project);
      setHistory((items) => items.map((item) => item.id === targetId
        ? { ...item, status: "cancelled" }
        : item));
    } catch (caught) {
      setError(caught.message || "取消视频任务失败");
    }
  }, [current]);

  const beginNewTask = useCallback(() => {
    operationVersion.current += 1;
    selectController.current?.abort();
    setIsLoading(false);
    setCurrent(null);
    setError("");
  }, []);

  return { beginNewTask, cancel, current, error, generate, history, isCreating, isLoading, refresh, select };
}

function upsert(items, project) {
  const summary = {
    id: project.id,
    title: project.title,
    request_text: project.request_text,
    status: project.status,
    requested_mode: project.requested_mode,
    origin: project.origin,
    created_at: project.created_at,
    updated_at: project.updated_at,
  };
  return [summary, ...items.filter((item) => item.id !== project.id)]
    .sort((left, right) => new Date(right.updated_at) - new Date(left.updated_at));
}
