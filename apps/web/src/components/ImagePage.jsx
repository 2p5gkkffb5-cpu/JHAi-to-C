import { useEffect, useRef, useState } from "react";
import { generateImage } from "../api/images.js";

const ASSET = "/brand/";
const sizes = [
  { value: "1024x1024", label: "方形", ratio: "1:1" },
  { value: "1536x1024", label: "横版", ratio: "3:2" },
  { value: "1024x1536", label: "竖版", ratio: "2:3" },
];
export function ImagePage({ initialPrompt = "", initialReferences = [] }) {
  const [prompt, setPrompt] = useState(initialPrompt);
  const [size, setSize] = useState(sizes[0].value);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [isGenerating, setIsGenerating] = useState(false);
  const abortRef = useRef(null);
  const referenceImages = initialReferences.filter(
    (reference) => reference?.type === "image" && typeof reference.snapshot?.url === "string",
  );

  useEffect(() => () => abortRef.current?.abort(), []);

  const submit = async (event) => {
    event?.preventDefault();
    const cleanPrompt = prompt.trim();
    if (!cleanPrompt || isGenerating) return;

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setIsGenerating(true);
    setError("");
    try {
      const input = {
        prompt: cleanPrompt,
        size,
      };
      if (referenceImages.length > 0) {
        input.images = referenceImages.map((reference) => reference.snapshot.url);
      }
      setResult(await generateImage(input, controller.signal));
    } catch (requestError) {
      if (requestError.name !== "AbortError") {
        setError(requestError.message || "图片生成失败，请稍后重试");
      }
    } finally {
      if (abortRef.current === controller) {
        abortRef.current = null;
        setIsGenerating(false);
      }
    }
  };

  const handlePromptKeyDown = (event) => {
    if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
      event.preventDefault();
      void submit();
    }
  };

  return (
    <main className="image-page">
      <div className="image-workspace">
        <header className="image-heading">
          <div>
            <p>AI 图片</p>
            <h1>把一个想法，变成一张可用的图</h1>
          </div>
          <span className="image-model-badge">gpt-image-2-vip · 1K</span>
        </header>

        <div className="image-layout">
          <form className="image-controls" onSubmit={submit}>
            <div className="image-field">
              <label htmlFor="image-prompt">画面描述</label>
              <span>{prompt.length}/8000</span>
              <textarea
                id="image-prompt"
                maxLength={8000}
                value={prompt}
                onChange={(event) => setPrompt(event.target.value)}
                onKeyDown={handlePromptKeyDown}
                placeholder="例如：雨后的上海街头，一家暖黄色灯光的咖啡店，电影感，真实摄影"
              />
              <small>写清主体、场景、光线与风格，效果会更稳定。</small>
            </div>

            {referenceImages.length > 0 && (
              <section className="image-references" aria-label="生成参考图">
                <div>
                  <strong>参考图</strong>
                  <span>生成时会参考图片内容与风格</span>
                </div>
                <ul>
                  {referenceImages.map((reference) => (
                    <li key={reference.id}>
                      <img src={reference.snapshot.url} alt={reference.label || "参考图"} />
                      <span>{reference.snapshot.filename || reference.label || "参考图"}</span>
                    </li>
                  ))}
                </ul>
              </section>
            )}

            <fieldset className="image-options">
              <legend>画面比例</legend>
              <div>
                {sizes.map((option) => (
                  <label className={size === option.value ? "is-selected" : ""} key={option.value}>
                    <input
                      type="radio"
                      name="image-size"
                      value={option.value}
                      checked={size === option.value}
                      onChange={() => setSize(option.value)}
                    />
                    <strong>{option.ratio}</strong>
                    <span>{option.label}</span>
                  </label>
                ))}
              </div>
            </fieldset>

            {error && <p className="image-error" role="alert">{error}</p>}
            <button className="image-generate" type="submit" disabled={!prompt.trim() || isGenerating}>
              {isGenerating ? <span className="image-button-spinner" aria-hidden="true" /> : <img src={`${ASSET}public-placeholder.svg`} alt="" />}
              {isGenerating ? "正在生成图片" : "生成图片"}
            </button>
            <p className="image-shortcut">⌘ / Ctrl + Enter 快速生成</p>
          </form>

          <section className="image-result" aria-live="polite" aria-busy={isGenerating}>
            {isGenerating ? (
              <div className={`image-result-skeleton size-${size}`}>
                <span />
                <p>正在构图与处理细节，通常需要一点时间</p>
              </div>
            ) : result ? (
              <figure>
                <img src={result.image_url} alt={prompt.trim() || "AI 生成图片"} />
                <figcaption>
                  <div>
                    <strong>生成完成</strong>
                    <span>{result.size}{referenceImages.length > 0 ? " · 已使用参考图" : ""}</span>
                  </div>
                  <a href={result.image_url} download="jhai-ai-image.png" target="_blank" rel="noreferrer">下载原图</a>
                </figcaption>
              </figure>
            ) : (
              <div className="image-empty">
                <img src={`${ASSET}public-placeholder.svg`} alt="" />
                <h2>生成结果会出现在这里</h2>
                <p>先描述你想看到的画面，再选择合适的比例。</p>
              </div>
            )}
          </section>
        </div>
      </div>
    </main>
  );
}
