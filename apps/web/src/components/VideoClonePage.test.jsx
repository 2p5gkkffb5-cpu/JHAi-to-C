import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useVideoGenerations } from "../hooks/useVideoGenerations.js";
import { useVideoMaterials } from "../hooks/useVideoMaterials.js";
import { VideoClonePage } from "./VideoClonePage.jsx";

vi.mock("../hooks/useVideoGenerations.js", () => ({ useVideoGenerations: vi.fn() }));
vi.mock("../hooks/useVideoMaterials.js", () => ({ useVideoMaterials: vi.fn() }));

const generate = vi.fn();
const reference = {
  filename: "参考.mp4",
  reference: { id: "reference-1", type: "reference_video", label: "@参考.mp4", snapshot: {} },
};
const replacement = {
  filename: "新品.png",
  reference: { id: "replacement-1", type: "product", label: "@新品.png", snapshot: {} },
};

function materialState(items) {
  return {
    addFiles: vi.fn(),
    error: "",
    isUploading: false,
    items,
    remove: vi.fn(),
    reset: vi.fn(),
  };
}

describe("VideoClonePage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    let materialCall = 0;
    const states = [
      materialState([{ localId: "reference", status: "uploaded", isVideo: true, previewUrl: "/reference.mp4", uploaded: reference }]),
      materialState([{ localId: "replacement", status: "uploaded", isVideo: false, previewUrl: "/replacement.png", uploaded: replacement }]),
    ];
    useVideoMaterials.mockImplementation(() => states[(materialCall++) % states.length]);
    useVideoGenerations.mockReturnValue({
      beginNewTask: vi.fn(),
      cancel: vi.fn(),
      current: null,
      error: "",
      generate,
      history: [],
      isCreating: false,
      isLoading: false,
      select: vi.fn(),
    });
  });

  it("submits an isolated clone task only after required materials and goal exist", async () => {
    render(<VideoClonePage enabled onBack={vi.fn()} />);
    expect(screen.queryByText("03 · 复刻类型")).not.toBeInTheDocument();
    expect(screen.queryByText("发布平台")).not.toBeInTheDocument();
    const submit = screen.getByRole("button", { name: "开始视频复刻" });
    expect(submit).toBeDisabled();

    fireEvent.change(screen.getByPlaceholderText(/把参考片的前三秒钩子/), {
      target: { value: "替换为新品卖点" },
    });
    expect(submit).toBeEnabled();
    fireEvent.click(submit);

    await waitFor(() => expect(generate).toHaveBeenCalledWith(expect.objectContaining({
      prompt: expect.stringContaining("改编目标：替换为新品卖点"),
      references: [reference.reference, replacement.reference],
      durationSeconds: 15,
      targetPlatform: "douyin",
    })));
    expect(generate.mock.calls[0][0].prompt).not.toContain("内容类型：");
    expect(generate.mock.calls[0][0].prompt).toContain("发布平台：抖音");
    expect(useVideoGenerations).toHaveBeenCalledWith({
      enabled: true,
      origin: "video_clone",
      requestedMode: "video_clone",
    });
  });

  it("rejects a non-video reference sample before upload", async () => {
    let materialCall = 0;
    const emptyStates = [materialState([]), materialState([])];
    useVideoMaterials.mockImplementation(() => emptyStates[(materialCall++) % emptyStates.length]);
    const { container } = render(<VideoClonePage enabled onBack={vi.fn()} />);
    const referenceInput = container.querySelector('input[type="file"][accept^="video/"]');

    fireEvent.change(referenceInput, {
      target: { files: [new File(["image"], "wrong.png", { type: "image/png" })] },
    });

    expect(await screen.findByRole("alert")).toHaveTextContent("参考样片必须是");
    expect(emptyStates[0].addFiles).not.toHaveBeenCalled();
  });
});
