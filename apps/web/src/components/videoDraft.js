const DRAFT_VERSION = 1;
const STORAGE_PREFIX = "jinghu:ai-video-draft";
const RATIOS = new Set(["9:16", "16:9", "1:1"]);
const DURATIONS = new Set([5, 10, 15]);

export function readVideoDraft(ownerId, storage = getDefaultStorage()) {
  if (!storage) return null;
  try {
    const raw = storage.getItem(storageKey(ownerId));
    if (!raw) return null;
    return normalizeDraft(JSON.parse(raw));
  } catch {
    return null;
  }
}

export function saveVideoDraft(ownerId, draft, storage = getDefaultStorage()) {
  if (!storage) throw new Error("当前浏览器无法保存草稿");
  const normalized = normalizeDraft({
    ...draft,
    version: DRAFT_VERSION,
    savedAt: new Date().toISOString(),
  });
  if (!normalized) throw new Error("草稿内容无效");
  storage.setItem(storageKey(ownerId), JSON.stringify(normalized));
  return normalized;
}

export function clearVideoDraft(ownerId, storage = getDefaultStorage()) {
  storage?.removeItem(storageKey(ownerId));
}

export function createVideoDraftSignature(draft) {
  const normalized = normalizeDraft({ ...draft, version: DRAFT_VERSION, savedAt: "" });
  if (!normalized) return "";
  return JSON.stringify({
    prompt: normalized.prompt,
    aspectRatio: normalized.aspectRatio,
    durationSeconds: normalized.durationSeconds,
    references: normalized.references,
  });
}

function normalizeDraft(value) {
  if (!value || typeof value !== "object" || value.version !== DRAFT_VERSION) return null;
  const prompt = typeof value.prompt === "string" ? value.prompt.slice(0, 5000) : "";
  const aspectRatio = RATIOS.has(value.aspectRatio) ? value.aspectRatio : "9:16";
  const durationSeconds = DURATIONS.has(value.durationSeconds) ? value.durationSeconds : 10;
  const references = Array.isArray(value.references)
    ? value.references.filter(isReference).slice(0, 10)
    : [];
  const savedAt = typeof value.savedAt === "string" ? value.savedAt : "";
  return { version: DRAFT_VERSION, prompt, aspectRatio, durationSeconds, references, savedAt };
}

function isReference(reference) {
  return Boolean(
    reference
    && typeof reference === "object"
    && typeof reference.id === "string"
    && typeof reference.type === "string"
    && typeof reference.label === "string"
    && reference.snapshot
    && typeof reference.snapshot === "object",
  );
}

function storageKey(ownerId) {
  return `${STORAGE_PREFIX}:v${DRAFT_VERSION}:${encodeURIComponent(ownerId || "guest")}`;
}

function getDefaultStorage() {
  return typeof window === "undefined" ? null : window.localStorage;
}
