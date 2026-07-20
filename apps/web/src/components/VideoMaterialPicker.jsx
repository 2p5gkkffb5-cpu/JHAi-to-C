import { useRef } from "react";

const ASSET = "/brand/";

export function VideoMaterialPicker({ items, onAdd, onInsert, onRemove }) {
  const inputRef = useRef(null);

  return (
    <section className="video-materials" aria-labelledby="video-material-title">
      <div className="video-section-label">
        <div>
          <strong id="video-material-title">素材</strong>
          <span>上传后在提示词里输入 @ 引用</span>
        </div>
        <button type="button" onClick={() => inputRef.current?.click()} disabled={items.length >= 10}>
          ＋ 添加素材
        </button>
        <input
          ref={inputRef}
          className="visually-hidden"
          type="file"
          accept="image/jpeg,image/png,image/webp,video/mp4,video/quicktime,video/webm"
          multiple
          onChange={(event) => {
            void onAdd(event.target.files || []);
            event.target.value = "";
          }}
        />
      </div>
      {items.length === 0 ? (
        <button className="video-material-empty" type="button" onClick={() => inputRef.current?.click()}>
          <img src={`${ASSET}public-placeholder.svg`} alt="" />
          <span><strong>添加图片或视频</strong><small>图片 10MB 内，视频 100MB 内</small></span>
        </button>
      ) : (
        <ul className="video-material-list">
          {items.map((item) => {
            const filename = item.uploaded?.filename || item.file?.name || "素材";
            return (
              <li className={`video-material-item is-${item.status}`} key={item.localId}>
                <button
                  className="video-material-preview"
                  type="button"
                  onClick={() => item.status === "uploaded" && onInsert(filename)}
                  disabled={item.status !== "uploaded"}
                  aria-label={`在提示词中引用 ${filename}`}
                >
                  {item.isVideo ? (
                    <video src={item.previewUrl} muted preload="metadata" />
                  ) : (
                    <img src={item.previewUrl} alt="" />
                  )}
                  {item.status === "uploading" && <span className="video-material-progress" />}
                  {item.isVideo && <span className="video-type-label">视频</span>}
                </button>
                <span title={filename}>@{filename}</span>
                <button className="video-material-remove" type="button" onClick={() => onRemove(item.localId)} aria-label={`移除 ${filename}`}>×</button>
                {item.status === "error" && <small title={item.error}>上传失败</small>}
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
