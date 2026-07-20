import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { MAX_IMAGE_COUNT } from "../hooks/useImageAttachment.js";
import { calculateAttachmentFanLayout, ImageAttachmentPicker } from "./ImageAttachmentPicker.jsx";

function imageFile(name = "reference.png") {
  return new File(["image"], name, { type: "image/png" });
}

function attachment(index) {
  return {
    file: imageFile(`reference-${index}.png`),
    id: `attachment-${index}`,
    previewUrl: `blob:attachment-${index}`,
    status: "uploaded",
  };
}

function renderPicker(props = {}) {
  const onSelect = props.onSelect || vi.fn();
  const result = render(
    <ImageAttachmentPicker
      attachments={[]}
      onRemove={vi.fn()}
      onRetry={vi.fn()}
      onSelect={onSelect}
      {...props}
    />,
  );
  return {
    ...result,
    onSelect,
    picker: result.container.querySelector(".image-attachment-picker"),
  };
}

describe("ImageAttachmentPicker", () => {
  it("keeps nested file drags active until the outer leave and selects once on drop", () => {
    const file = imageFile();
    const transfer = { files: [file], types: ["Files"] };
    const { onSelect, picker } = renderPicker();
    const addButton = screen.getByRole("button", { name: /添加参考图片/ });

    fireEvent.dragEnter(picker, { dataTransfer: transfer });
    fireEvent.dragEnter(addButton, { dataTransfer: transfer });
    fireEvent.dragLeave(addButton, { dataTransfer: transfer });
    expect(screen.getByRole("status")).toHaveTextContent("释放即可添加");

    fireEvent.drop(picker, { dataTransfer: transfer });
    expect(onSelect).toHaveBeenCalledTimes(1);
    expect(onSelect).toHaveBeenCalledWith([file]);
    expect(screen.queryByText("释放即可添加")).not.toBeInTheDocument();
  });

  it("ignores non-file, disabled, and full-capacity drops", () => {
    const file = imageFile();
    const onSelect = vi.fn();
    const { picker, rerender } = renderPicker({ disabled: true, onSelect });

    fireEvent.dragEnter(picker, { dataTransfer: { files: [file], types: ["text/plain"] } });
    fireEvent.drop(picker, { dataTransfer: { files: [file], types: ["Files"] } });
    expect(onSelect).not.toHaveBeenCalled();
    expect(screen.queryByText("释放即可添加")).not.toBeInTheDocument();

    rerender(
      <ImageAttachmentPicker
        attachments={Array.from({ length: MAX_IMAGE_COUNT }, (_, index) => attachment(index))}
        onRemove={vi.fn()}
        onRetry={vi.fn()}
        onSelect={onSelect}
      />,
    );
    fireEvent.drop(picker, { dataTransfer: { files: [file], types: ["Files"] } });
    expect(onSelect).not.toHaveBeenCalled();
  });

  it("compresses the fan layout to the available mobile width", () => {
    const layout = calculateAttachmentFanLayout(MAX_IMAGE_COUNT, 252);

    expect(layout.width).toBeLessThanOrEqual(252);
    expect(layout.step).toBeGreaterThan(0);
  });
});
