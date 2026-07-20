import { beforeEach, describe, expect, it, vi } from "vitest";
import { request } from "./client.js";
import { listProjects } from "./contentProjects.js";

vi.mock("./client.js", () => ({
  API_BASE_URL: "/api",
  request: vi.fn(),
}));

describe("listProjects", () => {
  beforeEach(() => vi.clearAllMocks());

  it("encodes the requested project origin in the query string", () => {
    const signal = new AbortController().signal;
    listProjects(signal, "video clone/实验");

    expect(request).toHaveBeenCalledWith(
      "/content-projects?origin=video%20clone%2F%E5%AE%9E%E9%AA%8C",
      { signal },
    );
  });
});
