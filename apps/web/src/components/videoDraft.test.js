import { beforeEach, describe, expect, it } from "vitest";
import {
  clearVideoDraft,
  createVideoDraftSignature,
  readVideoDraft,
  saveVideoDraft,
} from "./videoDraft.js";

const reference = {
  id: "asset-1",
  type: "image",
  label: "@商品.png",
  snapshot: {
    filename: "商品.png",
    content_type: "image/png",
    url: "/api/assets/asset-1/content",
  },
};

beforeEach(() => window.localStorage.clear());

describe("video draft storage", () => {
  it("restores the prompt, options, and uploaded material references", () => {
    saveVideoDraft("user-1", {
      version: 1,
      prompt: "让 @商品.png 缓慢旋转",
      aspectRatio: "16:9",
      durationSeconds: 15,
      references: [reference],
    });

    expect(readVideoDraft("user-1")).toMatchObject({
      prompt: "让 @商品.png 缓慢旋转",
      aspectRatio: "16:9",
      durationSeconds: 15,
      references: [reference],
    });
    expect(readVideoDraft("user-2")).toBeNull();
  });

  it("clears a saved draft when a new task begins", () => {
    saveVideoDraft("user-1", {
      version: 1,
      prompt: "测试草稿",
      aspectRatio: "9:16",
      durationSeconds: 10,
      references: [],
    });

    clearVideoDraft("user-1");
    expect(readVideoDraft("user-1")).toBeNull();
  });

  it("uses stable content signatures without the save timestamp", () => {
    const draft = {
      version: 1,
      prompt: "测试草稿",
      aspectRatio: "1:1",
      durationSeconds: 5,
      references: [reference],
    };

    expect(createVideoDraftSignature({ ...draft, savedAt: "first" }))
      .toBe(createVideoDraftSignature({ ...draft, savedAt: "second" }));
  });
});
