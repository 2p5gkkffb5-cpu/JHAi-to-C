import { useCallback, useEffect, useRef, useState } from "react";
import {
  cancelProject,
  createProject,
  getProject,
  getProjectEvents,
  getProjectResult,
  listProjects,
  selectStrategy,
  startProject,
  subscribeProjectEvents,
  submitAgentDecision,
} from "../api/contentProjects.js";

const TERMINAL_STATUSES = new Set(["completed", "failed", "cancelled"]);
const PROJECT_STORAGE_KEY = "jinghu-content-project-id";

export function useContentProject({ enabled = true, accountId = "guest" } = {}) {
  const storageKey = `${PROJECT_STORAGE_KEY}:${accountId}`;
  const [projectId, setProjectId] = useState(null);
  const [project, setProject] = useState(null);
  const [projects, setProjects] = useState([]);
  const [events, setEvents] = useState([]);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [isCreating, setIsCreating] = useState(false);
  const [isLoadingProjects, setIsLoadingProjects] = useState(false);
  const [projectsError, setProjectsError] = useState(null);
  const [isConfirming, setIsConfirming] = useState(false);
  const [isDeciding, setIsDeciding] = useState(false);
  const [isCancelling, setIsCancelling] = useState(false);
  const [streamVersion, setStreamVersion] = useState(0);
  const createController = useRef(null);
  const latestEventId = useRef(0);

  useEffect(() => {
    createController.current?.abort();
    latestEventId.current = 0;
    setProjectId(enabled ? window.sessionStorage.getItem(storageKey) : null);
    setProject(null);
    setProjects([]);
    setEvents([]);
    setResult(null);
    setError(null);
    setProjectsError(null);
  }, [enabled, storageKey]);

  const refreshProjects = useCallback(async (signal) => {
    if (!enabled) {
      setIsLoadingProjects(false);
      return;
    }
    setIsLoadingProjects(true);
    try {
      const nextProjects = await listProjects(signal, "agent");
      setProjects(nextProjects);
      setProjectsError(null);
    } catch (caught) {
      if (!signal?.aborted) {
        setProjectsError(toError(caught, "暂时无法读取历史对话"));
      }
    } finally {
      if (!signal?.aborted) setIsLoadingProjects(false);
    }
  }, [enabled]);

  useEffect(() => {
    if (!enabled) return undefined;
    const controller = new AbortController();
    void refreshProjects(controller.signal);
    return () => controller.abort();
  }, [enabled, refreshProjects]);

  useEffect(() => {
    latestEventId.current = 0;
    setEvents([]);
  }, [projectId]);

  useEffect(() => {
    if (!enabled || !projectId) return undefined;
    const controller = new AbortController();
    const applyProject = (nextProject) => {
      setProject(nextProject);
      setProjects((current) => upsertProjectSummary(current, nextProject));
      setError(null);
    };

    const loadOnceWithoutEventSource = async () => {
      try {
        const [nextProject, nextEvents] = await Promise.all([
          getProject(projectId, controller.signal),
          getProjectEvents(projectId, controller.signal, latestEventId.current),
        ]);
        applyProject(nextProject);
        if (nextEvents.length) {
          latestEventId.current = nextEvents[nextEvents.length - 1].id;
          setEvents((current) => mergeEvents(current, nextEvents));
        }
        if (nextProject.status === "completed") {
          setResult(await getProjectResult(projectId, controller.signal));
        }
      } catch (caught) {
        if (!controller.signal.aborted) {
          setError(toError(caught, "暂时无法读取任务状态"));
        }
      }
    };

    const unsubscribe = subscribeProjectEvents(projectId, {
      afterId: latestEventId.current,
      onEvent: (event) => {
        latestEventId.current = Math.max(latestEventId.current, event.id || 0);
        setEvents((current) => mergeEvents(current, [event]));
      },
      onProject: applyProject,
      onResult: (nextResult) => setResult(nextResult),
      onUnsupported: () => void loadOnceWithoutEventSource(),
    });
    return () => {
      controller.abort();
      unsubscribe();
    };
  }, [enabled, projectId, streamVersion]);

  useEffect(() => () => createController.current?.abort(), []);

  const createAndStart = useCallback(async (
    requestText,
    requestedMode = "auto",
    references = [],
  ) => {
    if (!enabled) throw new Error("请先登录后再创建任务");
    createController.current?.abort();
    const controller = new AbortController();
    createController.current = controller;
    setIsCreating(true);
    setError(null);
    setResult(null);
    try {
      const projectTitle = requestText.length > 60
        ? `${requestText.slice(0, 60)}…`
        : requestText;
      const created = await createProject({
        title: projectTitle,
        request_text: requestText,
        references,
        blueprint_id: null,
        target_platform: "douyin",
        duration_seconds: 10,
        aspect_ratio: "9:16",
        requested_mode: requestedMode,
        origin: "agent",
      }, controller.signal);
      await startProject(created.id, controller.signal);
      window.sessionStorage.setItem(storageKey, created.id);
      setProjectId(created.id);
      setProject(created);
      setProjects((current) => upsertProjectSummary(current, created));
      setEvents([]);
      return created;
    } catch (caught) {
      const nextError = toError(caught, "创建任务失败");
      if (!controller.signal.aborted) setError(nextError);
      throw nextError;
    } finally {
      if (createController.current === controller) {
        createController.current = null;
        setIsCreating(false);
      }
    }
  }, [enabled, storageKey]);

  const confirmStrategy = useCallback(async (strategyId) => {
    if (!projectId) return;
    setIsConfirming(true);
    setError(null);
    try {
      await selectStrategy(projectId, strategyId);
    } catch (caught) {
      const nextError = toError(caught, "方案确认失败");
      setError(nextError);
      throw nextError;
    } finally {
      setIsConfirming(false);
    }
  }, [projectId]);

  const decideAgent = useCallback(async ({ nodeName, action, feedback = "", strategyId = null }) => {
    if (!projectId) return;
    setIsDeciding(true);
    setError(null);
    try {
      await submitAgentDecision(projectId, {
        node_name: nodeName,
        action,
        feedback: feedback.trim() || null,
        strategy_id: strategyId,
      });
      setProject((current) => current && !TERMINAL_STATUSES.has(current.status)
        ? { ...current, status: "running" }
        : current);
    } catch (caught) {
      const nextError = toError(caught, action === "retry" ? "重新生成失败" : "无法继续任务");
      setError(nextError);
      throw nextError;
    } finally {
      setIsDeciding(false);
    }
  }, [projectId]);

  const cancel = useCallback(async () => {
    if (!projectId || TERMINAL_STATUSES.has(project?.status)) return;
    const controller = new AbortController();
    setIsCancelling(true);
    setError(null);
    try {
      const cancelled = await cancelProject(projectId, controller.signal);
      setProject((current) => current ? { ...current, status: cancelled.status } : current);
    } catch (caught) {
      const nextError = toError(caught, "取消任务失败");
      setError(nextError);
      throw nextError;
    } finally {
      setIsCancelling(false);
    }
  }, [projectId, project?.status]);

  const retry = useCallback(() => {
    setError(null);
    setStreamVersion((value) => value + 1);
  }, []);

  const selectProject = useCallback((nextProjectId) => {
    if (!nextProjectId || nextProjectId === projectId) return;
    createController.current?.abort();
    window.sessionStorage.setItem(storageKey, nextProjectId);
    setProjectId(nextProjectId);
    setProject(null);
    setResult(null);
    setError(null);
  }, [projectId, storageKey]);

  const reset = useCallback(() => {
    createController.current?.abort();
    window.sessionStorage.removeItem(storageKey);
    setProjectId(null);
    setProject(null);
    setEvents([]);
    setResult(null);
    setError(null);
    setIsCreating(false);
    setIsConfirming(false);
    setIsDeciding(false);
    setIsCancelling(false);
    latestEventId.current = 0;
  }, [storageKey]);

  return {
    projectId,
    project,
    projects,
    events,
    result,
    error,
    isCreating,
    isLoadingProjects,
    projectsError,
    isConfirming,
    isDeciding,
    isCancelling,
    createAndStart,
    selectProject,
    refreshProjects,
    confirmStrategy,
    decideAgent,
    cancel,
    retry,
    reset,
  };
}

function mergeEvents(current, incoming) {
  const byId = new Map(current.map((event) => [event.id, event]));
  incoming.forEach((event) => byId.set(event.id, event));
  return [...byId.values()].sort((left, right) => left.id - right.id);
}

function upsertProjectSummary(current, project) {
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
  return [summary, ...current.filter((item) => item.id !== summary.id)]
    .sort((left, right) => new Date(right.updated_at) - new Date(left.updated_at));
}

function toError(caught, fallback) {
  return caught instanceof Error ? caught : new Error(fallback);
}
