const configuredBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim();
const API_BASE_URL = (configuredBaseUrl || "/api").replace(/\/+$/, "");

export async function uploadImage(file, signal) {
  const query = new URLSearchParams({ filename: file.name });
  const response = await fetch(`${API_BASE_URL}/assets/images?${query}`, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": file.type,
    },
    body: file,
    credentials: "include",
    signal,
  });
  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json")
    ? await response.json()
    : await response.text();

  if (!response.ok) {
    const message =
      payload && typeof payload === "object" && typeof payload.detail === "string"
        ? payload.detail
        : typeof payload === "string" && payload
          ? payload
          : "图片上传失败，请稍后重试";
    throw new Error(message);
  }
  return payload;
}

export async function uploadMaterial(file, signal) {
  const query = new URLSearchParams({ filename: file.name });
  const response = await fetch(`${API_BASE_URL}/assets/materials?${query}`, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": file.type,
    },
    body: file,
    credentials: "include",
    signal,
  });
  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json")
    ? await response.json()
    : await response.text();

  if (!response.ok) {
    const message =
      payload && typeof payload === "object" && typeof payload.detail === "string"
        ? payload.detail
        : typeof payload === "string" && payload
          ? payload
          : "素材上传失败，请稍后重试";
    throw new Error(message);
  }
  return payload;
}
