export const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";
export const WS_URL = import.meta.env.VITE_WS_URL || "ws://localhost:8000/ws";

// Label -> color token + human name. Color is never the only cue (text badge too).
export const LABELS = {
  bug: { name: "Bug", color: "var(--c-bug)" },
  billing: { name: "Billing", color: "var(--c-billing)" },
  support: { name: "Support", color: "var(--c-support)" },
  praise: { name: "Praise", color: "var(--c-praise)" },
  feature_request: { name: "Feature request", color: "var(--c-feature)" },
};
export const labelMeta = (l) => LABELS[l] || { name: l, color: "var(--muted)" };

// Matches LOW_CONFIDENCE in the backend config (events under this are "low" / need review)
export const LOW_CONFIDENCE = 0.5;
