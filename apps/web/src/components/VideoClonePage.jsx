import { useMemo, useState } from "react";
import { useVideoGenerations } from "../hooks/useVideoGenerations.js";
import { useVideoMaterials } from "../hooks/useVideoMaterials.js";
import { VideoHistory } from "./VideoHistory.jsx";
import { VideoPreview } from "./VideoPage.jsx";
import { VideoCloneMaterialField } from "./VideoCloneMaterialField.jsx";
import { VideoCloneOutputs } from "./VideoCloneOutputs.jsx";
import {
  buildVideoCloneRequest,
  videoCloneLevels,
  videoCloneSteps,
  videoCloneTargetPlatform,
} from "./videoCloneConfig.js";

const ratios = ["9:16", "16:9", "1:1"];
const durations = [5, 10, 15];
const ACTIVE_STATUSES = new Set(["draft", "running", "generating", "reviewing"]);

export function VideoClonePage({ enabled, onBack }) {
  const [cloneLevel, setCloneLevel] = useState(videoCloneLevels[1].value);
  const [goal, setGoal] = useState("");
  const [aspectRatio, setAspectRatio] = useState("9:16");
  const [durationSeconds, setDurationSeconds] = useState(15);
  const [localError, setLocalError] = useState("");
  const reference = useVideoMaterials();
  const replacements = useVideoMaterials();
  const generations = useVideoGenerations({
    enabled,
    origin: "video_clone",
    requestedMode: "video_clone",
  });

  const uploadedReference = reference.items.find((item) => item.uploaded?.reference)?.uploaded;
  const uploadedReplacements = useMemo(
    () => replacements.items.flatMap((item) => item.uploaded?.reference ? [item.uploaded] : []),
    [replacements.items],
  );
  const isUploading = reference.isUploading || replacements.isUploading;
  const isActive = ACTIVE_STATUSES.has(generations.current?.status);
  const canGenerate = Boolean(uploadedReference && uploadedReplacements.length && goal.trim())
    && !isUploading
    && !generations.isCreating
    && !isActive;

  const addReference = async (files) => {
    const [file] = [...files];
    setLocalError("");
    if (!file) return;
    if (!file.type.startsWith("video/")) {
      setLocalError("参考样片必须是 MP4、MOV 或 WebM 视频");
      return;
    }
    await reference.addFiles([file]);
  };

  const submit = async (event) => {
    event.preventDefault();
    if (!canGenerate) return;
    setLocalError("");
    const prompt = buildVideoCloneRequest({
      cloneLevel,
      goal,
      referenceFilename: uploadedReference.filename,
      replacementFilenames: uploadedReplacements.map((item) => item.filename),
    });
    await generations.generate({
      prompt,
      references: [uploadedReference.reference, ...uploadedReplacements.map((item) => item.reference)],
      durationSeconds,
      aspectRatio,
      targetPlatform: videoCloneTargetPlatform.value,
    });
  };

  const reset = () => {
    reference.reset();
    replacements.reset();
    generations.beginNewTask();
    setCloneLevel(videoCloneLevels[1].value);
    setGoal("");
    setAspectRatio("9:16");
    setDurationSeconds(10);
    setLocalError("");
  };

  return (
    <main className="video-clone-page">
      <div className="video-clone-workspace">
        <header className="video-clone-page-heading">
          <button type="button" onClick={onBack} aria-label="返回首页">←</button>
          <div><p>VIDEO RE-CREATION</p><h1>视频复刻</h1><span>拆爆点、换素材、重做表达，形成一条独立的新视频。</span></div>
          <button type="button" onClick={reset} disabled={isUploading || isActive}>＋ 新建复刻</button>
        </header>

        <ol className="video-clone-page-flow" aria-label="视频复刻流程">
          {videoCloneSteps.map(([number, title, description]) => (
            <li key={number}><span>{number}</span><div><strong>{title}</strong><small>{description}</small></div></li>
          ))}
        </ol>

        <div className="video-clone-page-layout">
          <VideoHistory currentId={generations.current?.id} history={generations.history} isLoading={generations.isLoading} onSelect={generations.select} />

          <section className="video-clone-studio" aria-label="视频复刻工作台">
            <VideoPreview current={generations.current} isLoading={generations.isLoading} />
            <VideoCloneOutputs current={generations.current} />

            <form className="video-clone-form" onSubmit={(event) => void submit(event).catch(() => {})}>
              <div className="video-clone-materials-grid">
                <VideoCloneMaterialField
                  accept="video/mp4,video/quicktime,video/webm"
                  emptyTitle="上传参考样片"
                  emptyDescription="用于拆解钩子、节奏与镜头语言，100MB 内"
                  items={reference.items}
                  maxItems={1}
                  onAdd={addReference}
                  onRemove={reference.remove}
                  title="01 · 参考样片"
                />
                <VideoCloneMaterialField
                  accept="image/jpeg,image/png,image/webp,video/mp4,video/quicktime,video/webm"
                  emptyTitle="上传替换素材"
                  emptyDescription="商品、人物、品牌或场景素材，最多 10 个"
                  items={replacements.items}
                  maxItems={10}
                  onAdd={replacements.addFiles}
                  onRemove={replacements.remove}
                  title="02 · 替换素材"
                />
              </div>

              <div className="video-clone-parameters">
                <label><span>复刻强度</span><select value={cloneLevel} onChange={(event) => setCloneLevel(event.target.value)}>{videoCloneLevels.map((item) => <option value={item.value} key={item.value}>{item.value}</option>)}</select></label>
                <label><span>画面比例</span><select value={aspectRatio} onChange={(event) => setAspectRatio(event.target.value)}>{ratios.map((item) => <option value={item} key={item}>{item}</option>)}</select></label>
                <label><span>目标时长</span><select value={durationSeconds} onChange={(event) => setDurationSeconds(Number(event.target.value))}>{durations.map((item) => <option value={item} key={item}>{item} 秒</option>)}</select></label>
              </div>

              <label className="video-clone-goal"><span>03 · 改编目标</span><textarea maxLength={5000} value={goal} onChange={(event) => setGoal(event.target.value)} placeholder="例如：把参考片的前三秒钩子换成我的护肤品卖点，面向 25—35 岁女性；保留快节奏切镜，重写台词和场景。" /></label>

              {(localError || reference.error || replacements.error || generations.error) && <p className="video-error" role="alert">{localError || reference.error || replacements.error || generations.error}</p>}
              <footer className="video-clone-submit-row">
                <p>复刻任务与 AI 视频任务完全分开保存，互不影响历史与草稿。</p>
                {isActive && <button type="button" onClick={() => void generations.cancel()}>取消本次复刻</button>}
                <button className="is-primary" type="submit" disabled={!canGenerate}>{generations.isCreating || isActive ? "正在复刻" : "开始视频复刻"}</button>
              </footer>
            </form>
          </section>
        </div>
      </div>
    </main>
  );
}
