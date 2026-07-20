import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { VideoPage } from "./VideoPage.jsx";
import { saveVideoDraft } from "./videoDraft.js";

vi.mock("../hooks/useVideoGenerations.js", () => ({
  useVideoGenerations: () => ({
    beginNewTask: vi.fn(),
    cancel: vi.fn(),
    current: null,
    error: "",
    generate: vi.fn(),
    history: [],
    isCreating: false,
    isLoading: false,
    select: vi.fn(),
  }),
}));

vi.mock("../hooks/useVideoMaterials.js", () => ({
  useVideoMaterials: () => ({
    addFiles: vi.fn(),
    error: "",
    isUploading: false,
    items: [],
    remove: vi.fn(),
    reset: vi.fn(),
  }),
}));

describe("VideoPage", () => {
  beforeEach(() => window.localStorage.clear());

  it("consumes entry seed once and lets a new task stay empty", async () => {
    const onInitialInputConsumed = vi.fn();
    render(
      <VideoPage
        enabled
        ownerId="user-1"
        initialPrompt="一次性入口提示词"
        onInitialInputConsumed={onInitialInputConsumed}
      />,
    );

    expect(screen.getByLabelText("视频描述")).toHaveValue("一次性入口提示词");
    await waitFor(() => expect(onInitialInputConsumed).toHaveBeenCalledTimes(1));

    fireEvent.click(screen.getByRole("button", { name: /新建任务/ }));
    expect(screen.getByLabelText("视频描述")).toHaveValue("");
  });

  it("restores a saved account draft when no entry seed is present", () => {
    saveVideoDraft("user-1", {
      version: 1,
      prompt: "恢复这条已保存草稿",
      aspectRatio: "16:9",
      durationSeconds: 15,
      references: [],
    });

    render(<VideoPage enabled ownerId="user-1" />);

    expect(screen.getByLabelText("视频描述")).toHaveValue("恢复这条已保存草稿");
    expect(screen.getByRole("radio", { name: "16:9" })).toBeChecked();
    expect(screen.getByRole("combobox", { name: "时长" })).toHaveValue("15");
  });
});
