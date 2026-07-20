import { API_BASE_URL, request } from "./client.js";

function projectPath(projectId, suffix = "") {
  return `/content-projects/${encodeURIComponent(projectId)}${suffix}`;
}

export function createProject(input, signal) {
  return request("/content-projects", {
    method: "POST",
    body: JSON.stringify(input),
    signal,
  });
}

export function listProjects(signal, origin) {
  const query = origin ? `?origin=${encodeURIComponent(origin)}` : "";
  return request(`/content-projects${query}`, { signal });
}

export function startProject(projectId, signal) {
  return request(projectPath(projectId, "/start"), { method: "POST", signal });
}

export function getProject(projectId, signal) {
  return request(projectPath(projectId), { signal });
}

export function getProjectEvents(projectId, signal, afterId) {
  const query = afterId ? `?after_id=${encodeURIComponent(afterId)}` : "";
  return request(projectPath(projectId, `/events${query}`), { signal });
}

export function subscribeProjectEvents(
  projectId,
  { afterId = 0, onEvent, onProject, onResult, onUnsupported } = {},
) {
  if (typeof window === "undefined" || typeof window.EventSource === "undefined") {
    onUnsupported?.();
    return () => {};
  }

  const query = `?after_id=${encodeURIComponent(afterId)}`;
  const eventSource = new window.EventSource(
    `${API_BASE_URL}${projectPath(projectId, `/events/stream${query}`)}`,
    { withCredentials: true },
  );
  const parseFrame = (event, handler) => {
    try {
      handler?.(JSON.parse(event.data));
    } catch {
      // Ignore one malformed frame. EventSource will continue consuming the stream.
    }
  };
  const handleEvent = (event) => parseFrame(event, onEvent);
  const handleProject = (event) => parseFrame(event, onProject);
  const handleResult = (event) => parseFrame(event, onResult);
  eventSource.addEventListener("project_event", handleEvent);
  eventSource.addEventListener("project_state", handleProject);
  eventSource.addEventListener("project_result", handleResult);

  return () => {
    eventSource.removeEventListener("project_event", handleEvent);
    eventSource.removeEventListener("project_state", handleProject);
    eventSource.removeEventListener("project_result", handleResult);
    eventSource.close();
  };
}

export function selectStrategy(projectId, strategyId, signal) {
  return request(projectPath(projectId, "/strategy-selection"), {
    method: "POST",
    body: JSON.stringify({ strategy_id: strategyId }),
    signal,
  });
}

export function submitAgentDecision(projectId, decision, signal) {
  return request(projectPath(projectId, "/agent-decisions"), {
    method: "POST",
    body: JSON.stringify(decision),
    signal,
  });
}

export function cancelProject(projectId, signal) {
  return request(projectPath(projectId, "/cancel"), {
    method: "POST",
    signal,
  });
}

export function getProjectResult(projectId, signal) {
  return request(projectPath(projectId, "/result"), { signal });
}
