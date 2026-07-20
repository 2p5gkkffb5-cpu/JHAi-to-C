import { request } from "./client.js";

export async function generateImage(input, signal) {
  return request("/images/generations", {
    method: "POST",
    body: JSON.stringify(input),
    signal,
  });
}
