import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { AgentTurn } from "./AgentTurn.jsx";

const meta = {
  activeTitle: "正在执行",
  completed: "执行完成",
  completedTitle: "已经完成",
  name: "测试 Agent",
  thinking: "正在处理",
};

function turn(status) {
  return {
    attempt: 1,
    decision: null,
    id: "director-1",
    meta,
    nodeName: "director",
    status,
    summary: "执行完成",
    tools: [],
  };
}

describe("AgentTurn", () => {
  it("renders cancelled turns as stopped instead of completed", () => {
    render(<AgentTurn isAwaiting={false} step={1} turn={turn("cancelled")} />);

    expect(screen.getByRole("article")).toHaveClass("is-cancelled");
    expect(screen.getByRole("heading", { name: "这一步已停止" })).toBeVisible();
    expect(screen.getByText("当前任务已取消，这一步不会再继续执行。")).toBeVisible();
    expect(screen.queryByText(meta.completedTitle)).not.toBeInTheDocument();
  });

  it("keeps failed and completed copy distinct", () => {
    const { rerender } = render(<AgentTurn isAwaiting={false} step={1} turn={turn("failed")} />);
    expect(screen.getByRole("heading", { name: "这一步需要缓一缓" })).toBeVisible();

    rerender(<AgentTurn isAwaiting={false} step={1} turn={turn("completed")} />);
    expect(screen.getByRole("heading", { name: meta.completedTitle })).toBeVisible();
  });
});
