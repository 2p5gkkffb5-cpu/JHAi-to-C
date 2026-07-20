import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { CanvasPage, getCanvasStorageKey } from "./CanvasPage.jsx";

describe("CanvasPage", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("adds a video node and reports a missing input without pretending to generate", () => {
    vi.useFakeTimers();
    render(<CanvasPage ownerId="user-1" />);
    expect(screen.getByRole("region", { name: "快捷开始" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "添加节点" }));
    fireEvent.click(screen.getByRole("button", { name: /视频.*动态镜头片段/ }));
    expect(screen.getByRole("heading", { name: "新视频片段" })).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "快捷开始" })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "预览路径" }));
    expect(screen.getAllByText("缺少输入")).toHaveLength(1);
    expect(screen.getByRole("note")).toHaveTextContent("不会执行生成");
  });

  it("isolates saved workspaces by account", () => {
    window.localStorage.setItem(getCanvasStorageKey("user-1"), JSON.stringify({
      title: "用户一画布",
      nodes: [],
      edges: [],
    }));
    window.localStorage.setItem(getCanvasStorageKey("user-2"), JSON.stringify({
      title: "用户二画布",
      nodes: [],
      edges: [],
    }));

    const { rerender } = render(<CanvasPage key="user-1" ownerId="user-1" />);
    expect(screen.getByLabelText("工作区名称")).toHaveValue("用户一画布");

    rerender(<CanvasPage key="user-2" ownerId="user-2" />);
    expect(screen.getByLabelText("工作区名称")).toHaveValue("用户二画布");
  });

  it("falls back safely when a saved workspace is corrupted", () => {
    window.localStorage.setItem(getCanvasStorageKey("user-1"), "{broken-json");
    render(<CanvasPage ownerId="user-1" />);

    expect(screen.getByLabelText("工作区名称")).toHaveValue("未命名工作区");
    expect(screen.getByRole("region", { name: "快捷开始" })).toBeInTheDocument();
  });
});
