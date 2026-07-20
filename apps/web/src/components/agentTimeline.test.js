import { describe, expect, it } from "vitest";
import { deriveAgentTurns } from "./agentTimeline.js";

const updatedAt = "2026-07-20T08:00:00Z";

function project(overrides = {}) {
  return {
    artifacts: {},
    current_node: "director",
    status: "running",
    updated_at: updatedAt,
    ...overrides,
  };
}

function startedEvent(overrides = {}) {
  return {
    created_at: updatedAt,
    event_type: "node.started",
    id: 1,
    node_name: "director",
    payload: { task_id: "task-1" },
    ...overrides,
  };
}

describe("deriveAgentTurns", () => {
  it("keeps one fallback turn while an active project has no events", () => {
    const turns = deriveAgentTurns(project(), []);

    expect(turns).toHaveLength(1);
    expect(turns[0]).toMatchObject({
      id: "director-current",
      nodeName: "director",
      status: "running",
    });
  });

  it("projects cancellation onto an existing running turn", () => {
    const turns = deriveAgentTurns(project({ status: "cancelled" }), [startedEvent()]);

    expect(turns).toHaveLength(1);
    expect(turns[0].status).toBe("cancelled");
  });

  it("creates a cancelled fallback when cancellation arrives before events", () => {
    const turns = deriveAgentTurns(project({ status: "cancelled" }), []);

    expect(turns).toHaveLength(1);
    expect(turns[0].status).toBe("cancelled");
  });

  it.each(["completed", "failed"])("does not overwrite a %s turn during cancellation", (eventStatus) => {
    const terminalEvent = {
      ...startedEvent({ id: 2 }),
      event_type: eventStatus === "failed" ? "node.failed" : "node.completed",
      payload: { output: { value: true }, summary: "done", task_id: "task-1" },
    };
    const turns = deriveAgentTurns(project({ status: "cancelled" }), [startedEvent(), terminalEvent]);

    expect(turns[0].status).toBe(eventStatus);
  });
});
