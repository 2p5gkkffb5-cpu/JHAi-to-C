import { useRef } from "react";

export function VideoCloneMaterialField({
  accept,
  emptyDescription,
  emptyTitle,
  items,
  maxItems,
  onAdd,
  onRemove,
  title,
}) {
  const inputRef = useRef(null);
  const canAdd = items.length < maxItems;

  return (
    <section className="video-clone-material-field" aria-label={title}>
      <header>
        <div><strong>{title}</strong><span>{items.length}/{maxItems}</span></div>
        {canAdd && <button type="button" onClick={() => inputRef.current?.click()}>＋ 添加</button>}
        <input
          ref={inputRef}
          className="visually-hidden"
          type="file"
          accept={accept}
          multiple={maxItems > 1}
          onChange={(event) => {
            void onAdd(event.target.files || []);
            event.target.value = "";
          }}
        />
      </header>

      {items.length === 0 ? (
        <button className="video-clone-material-empty" type="button" onClick={() => inputRef.current?.click()}>
          <span aria-hidden="true">＋</span>
          <strong>{emptyTitle}</strong>
          <small>{emptyDescription}</small>
        </button>
      ) : (
        <ul className="video-clone-material-list">
          {items.map((item) => {
            const filename = item.uploaded?.filename || item.file?.name || "素材";
            return (
              <li className={`is-${item.status}`} key={item.localId}>
                <div>
                  {item.isVideo ? <video src={item.previewUrl} muted preload="metadata" /> : <img src={item.previewUrl} alt="" />}
                  {item.status === "uploading" && <span className="video-material-progress" />}
                </div>
                <span title={filename}><strong>{filename}</strong><small>{item.status === "uploaded" ? "已上传" : item.status === "error" ? "上传失败" : "上传中"}</small></span>
                <button type="button" onClick={() => onRemove(item.localId)} aria-label={`移除 ${filename}`}>×</button>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
