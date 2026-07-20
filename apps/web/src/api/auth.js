import { request } from "./client.js";

export function getCurrentUser(signal) {
  return request("/auth/me", { signal });
}

export function login(input, signal) {
  return request("/auth/login", {
    method: "POST",
    body: JSON.stringify(input),
    signal,
  });
}

export function register(input, signal) {
  return request("/auth/register", {
    method: "POST",
    body: JSON.stringify(input),
    signal,
  });
}

export function logout(signal) {
  return request("/auth/logout", { method: "POST", signal });
}

export function getAccessConfiguration(signal) {
  return request("/access", { signal });
}

export function updateRolePermissions(roleId, permissions, signal) {
  return request(`/access/roles/${encodeURIComponent(roleId)}`, {
    method: "PATCH",
    body: JSON.stringify({ permissions }),
    signal,
  });
}

export function updateUserAccess(userId, input, signal) {
  return request(`/access/users/${encodeURIComponent(userId)}`, {
    method: "PATCH",
    body: JSON.stringify(input),
    signal,
  });
}
