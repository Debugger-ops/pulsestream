import { API_URL } from "./config.js";

async function request(path, options) {
  const res = await fetch(`${API_URL}${path}`, options);
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try { const body = await res.json(); if (body.detail) detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail); } catch { /* keep status text */ }
    throw new Error(detail);
  }
  return res.json();
}

const post = (path, body) => request(path, {
  method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body),
});

export const classifyText = (text) => post("/classify", { text });
export const sendFeedback = (event_id, correct_label, text) => post("/feedback", { event_id, correct_label, text });
export const getFeedbackSummary = () => request("/feedback");
export const exportUrl = (params) => {
  const qs = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => { if (v !== undefined && v !== "" && v !== false && v !== 0) qs.set(k, v); });
  return `${API_URL}/events/export.csv${qs.toString() ? `?${qs}` : ""}`;
};
