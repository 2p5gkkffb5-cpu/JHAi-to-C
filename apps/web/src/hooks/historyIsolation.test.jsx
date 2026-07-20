import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  cancelProject,
  createProject,
  getProject,
  listProjects,
  startProject,
  subscribeProjectEvents,
} from "../api/contentProjects.js";
import { useContentProject } from "./useContentProject.js";
import { useVideoGenerations } from "./useVideoGenerations.js";

vi.mock("../api/contentProjects.js", () => ({
  cancelProject: vi.fn(),
  createProject: vi.fn(),
  getProject: vi.fn(),
  getProjectEvents: vi.fn(),
  getProjectResult: vi.fn(),
  listProjects: vi.fn(),
  selectStrategy: vi.fn(),
  startProject: vi.fn(),
  subscribeProjectEvents: vi.fn(),
  submitAgentDecision: vi.fn(),
}));

const project = {
  id: "project-1",
  title: "测试任务",
  request_text: "生成一条测试视频",
  requested_mode: "video_generation",
  status: "draft",
  created_at: "2026-07-20T00:00:00Z",
  updated_at: "2026-07-20T00:00:00Z",
};

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, reject, resolve };
}

beforeEach(() => {
  window.sessionStorage.clear();
  vi.clearAllMocks();
  listProjects.mockResolvedValue([]);
  startProject.mockResolvedValue({ status: "queued" });
  subscribeProjectEvents.mockReturnValue(() => {});
});

describe("project history isolation", () => {
  it("only queries and creates Agent projects in the Agent workspace", async () => {
    createProject.mockResolvedValue({ ...project, origin: "agent" });
    const { result } = renderHook(() => useContentProject({ accountId: "user-1" }));

    await waitFor(() => expect(listProjects).toHaveBeenCalledWith(expect.any(AbortSignal), "agent"));
    await act(async () => {
      await result.current.createAndStart("生成一条测试视频", "video_generation");
    });

    expect(createProject).toHaveBeenCalledWith(
      expect.objectContaining({ origin: "agent" }),
      expect.any(AbortSignal),
    );
  });

  it("only queries and creates AI video projects in the video workspace", async () => {
    createProject.mockResolvedValue({ ...project, origin: "ai_video" });
    const { result } = renderHook(() => useVideoGenerations({ enabled: true }));

    await waitFor(() => expect(listProjects).toHaveBeenCalledWith(expect.any(AbortSignal), "ai_video"));
    await act(async () => {
      await result.current.generate({
        prompt: "生成一条测试视频",
        references: [],
        durationSeconds: 10,
        aspectRatio: "9:16",
      });
    });

    expect(createProject).toHaveBeenCalledWith(
      expect.objectContaining({ origin: "ai_video" }),
      expect.any(AbortSignal),
    );
  });

  it("keeps video clone projects in their own history", async () => {
    createProject.mockResolvedValue({ ...project, origin: "video_clone" });
    const { result } = renderHook(() => useVideoGenerations({ enabled: true, origin: "video_clone" }));

    await waitFor(() => expect(listProjects).toHaveBeenCalledWith(expect.any(AbortSignal), "video_clone"));
    await act(async () => {
      await result.current.generate({
        prompt: "复刻这条参考视频",
        references: [],
        durationSeconds: 10,
        aspectRatio: "9:16",
        targetPlatform: "xiaohongshu",
      });
    });

    expect(createProject).toHaveBeenCalledWith(
      expect.objectContaining({ origin: "video_clone", target_platform: "xiaohongshu" }),
      expect.any(AbortSignal),
    );
  });

  it("does not let a slow initial refresh overwrite a newly created task", async () => {
    const historyRequest = deferred();
    listProjects.mockReturnValueOnce(historyRequest.promise);
    createProject.mockResolvedValue({ ...project, id: "new-project", origin: "ai_video" });
    getProject.mockResolvedValue({ ...project, id: "old-project", origin: "ai_video" });
    const { result } = renderHook(() => useVideoGenerations({ enabled: true }));

    await act(async () => {
      await result.current.generate({
        prompt: "生成新视频",
        references: [],
        durationSeconds: 10,
        aspectRatio: "9:16",
      });
    });
    act(() => historyRequest.resolve([{ ...project, id: "old-project", origin: "ai_video" }]));

    await waitFor(() => expect(result.current.current?.id).toBe("new-project"));
    expect(result.current.history.map((item) => item.id)).toEqual(["new-project"]);
    expect(result.current.isLoading).toBe(false);
  });

  it("settles a stale initial loading state when starting a blank task", async () => {
    const historyRequest = deferred();
    listProjects.mockReturnValueOnce(historyRequest.promise);
    const { result } = renderHook(() => useVideoGenerations({ enabled: true }));
    await waitFor(() => expect(result.current.isLoading).toBe(true));

    act(() => result.current.beginNewTask());
    expect(result.current.isLoading).toBe(false);

    act(() => historyRequest.resolve([]));
    await waitFor(() => expect(result.current.isLoading).toBe(false));
  });

  it("keeps the latest history selection when responses finish out of order", async () => {
    const first = deferred();
    const second = deferred();
    getProject.mockImplementation((projectId) => (
      projectId === "first-project" ? first.promise : second.promise
    ));
    const { result } = renderHook(() => useVideoGenerations({ enabled: true }));
    await waitFor(() => expect(listProjects).toHaveBeenCalled());

    let firstSelection;
    let secondSelection;
    act(() => {
      firstSelection = result.current.select("first-project");
      secondSelection = result.current.select("second-project");
    });
    await act(async () => {
      second.resolve({ ...project, id: "second-project", origin: "ai_video" });
      await secondSelection;
    });
    await act(async () => {
      first.resolve({ ...project, id: "first-project", origin: "ai_video" });
      await firstSelection;
    });

    expect(result.current.current?.id).toBe("second-project");
  });

  it("does not mark a newly selected record cancelled when an older cancel finishes", async () => {
    const cancellation = deferred();
    cancelProject.mockReturnValueOnce(cancellation.promise);
    createProject.mockResolvedValue({ ...project, id: "first-project", origin: "ai_video" });
    getProject.mockResolvedValue({ ...project, id: "second-project", origin: "ai_video" });
    const { result } = renderHook(() => useVideoGenerations({ enabled: true }));
    await waitFor(() => expect(listProjects).toHaveBeenCalled());
    await act(async () => {
      await result.current.generate({
        prompt: "生成第一条视频",
        references: [],
        durationSeconds: 10,
        aspectRatio: "9:16",
      });
    });

    let cancelRequest;
    act(() => { cancelRequest = result.current.cancel(); });
    await act(async () => { await result.current.select("second-project"); });
    await act(async () => {
      cancellation.resolve({ status: "cancelled" });
      await cancelRequest;
    });

    expect(result.current.current).toMatchObject({ id: "second-project", status: "draft" });
    expect(result.current.history.find((item) => item.id === "first-project")?.status)
      .toBe("cancelled");
  });
});
