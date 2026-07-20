const configuredBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim();
export const API_BASE_URL = (configuredBaseUrl || "/api").replace(/\/+$/, "");

export class ApiError extends Error {
  constructor(status, message, payload) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.payload = payload;
  }
}

export async function request(path, init = {}) {
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  if (init.body !== undefined) headers.set("Content-Type", "application/json");

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers,
    credentials: "include",
  });
  if (response.status === 204) return null;

  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json")
    ? await response.json()
    : await response.text();

  if (!response.ok) {
    const message = getErrorMessage(payload, response.statusText);
    throw new ApiError(response.status, message, payload);
  }
  return payload;
}

function getErrorMessage(payload, fallback) {
  if (payload && typeof payload === "object" && typeof payload.detail === "string") {
    return payload.detail;
  }
  if (Array.isArray(payload?.detail)) {
    return payload.detail.map((item) => item.msg).filter(Boolean).join("；") || fallback;
  }
  if (typeof payload === "string" && payload) return payload;
  return fallback || "请求失败";
}
