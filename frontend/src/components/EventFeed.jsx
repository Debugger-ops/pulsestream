import { useEffect, useState } from "react";
import { LABELS, LOW_CONFIDENCE, labelMeta } from "../config.js";
import { sendFeedback } from "../api.js";

function ago(ts, now) {
  const s = Math.max(0, Math.round(now / 1000 - ts));
  if (s < 5) return "just now";
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  return `${Math.floor(s / 3600)}h ago`;
}

function Correct({ event, onCorrected }) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const choose = async (label) => {
    setBusy(true); setError(null);
    try {
      await sendFeedback(event.id, label, event.text);
      onCorrected(event.id, label);
      setOpen(false);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  if (!open) {
    return <button className="btn btn-ghost btn-sm" onClick={() => setOpen(true)}>
      {event.corrected_label ? "Change" : "Wrong label?"}
    </button>;
  }
  return (
    <span className="correct">
      <label className="sr-only" htmlFor={`fix-${event.id}`}>Correct label</label>
      <select id={`fix-${event.id}`} className="input input-sm" disabled={busy} autoFocus
              defaultValue={event.corrected_label || event.label}
              onChange={(e) => choose(e.target.value)} onKeyDown={(e) => e.key === "Escape" && setOpen(false)}>
        {Object.entries(LABELS).map(([key, m]) => <option key={key} value={key}>{m.name}</option>)}
      </select>
      <button className="btn btn-ghost btn-sm" onClick={() => setOpen(false)}>Cancel</button>
      {error && <span className="conf-low" role="alert">{error}</span>}
    </span>
  );
}

export default function EventFeed({ events, total, status, onCorrected }) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);

  if (events.length === 0) {
    return (
      <div className="empty">
        {total > 0 ? (
          <>No events match your filters.</>
        ) : status === "live" ? (
          <>Waiting for events…<small>Start the producer: <code>python3 producer/producer.py</code></small></>
        ) : (
          <>Can’t reach the backend yet.<small>Start it: <code>uvicorn backend.app:app --port 8000</code></small></>
        )}
      </div>
    );
  }

  return (
    <ul className="feed">
      {events.map((e) => {
        const m = labelMeta(e.label);
        const pct = Math.round(e.confidence * 100);
        const low = e.confidence < LOW_CONFIDENCE;
        return (
          <li key={e.id} className="event" style={{ "--accent": m.color }}>
            <div className="event-top">
              <span className="badge" style={{ color: m.color, borderColor: m.color }}>{m.name}</span>
              <span className="conf" title={`Confidence ${pct}%`}>
                <span className="conf-track"><span className="conf-fill" style={{ width: `${pct}%`, background: m.color }} /></span>
                <span className={low ? "conf-low" : ""}>{pct}%{low ? " · low" : ""}</span>
              </span>
              {e.corrected_label && (
                <span className="badge badge-fixed" style={{ color: labelMeta(e.corrected_label).color, borderColor: labelMeta(e.corrected_label).color }}
                      title={`A person corrected this to ${labelMeta(e.corrected_label).name}`}>
                  ✓ {labelMeta(e.corrected_label).name}
                </span>
              )}
              <span className="event-meta">{ago(e.ts, now)}</span>
            </div>
            <p className="event-text">{e.text}</p>
            <div className="event-foot">
              {(e.top || []).slice(1).map((t) => (
                <span key={t.label} className="runner">{labelMeta(t.label).name} {Math.round(t.confidence * 100)}%</span>
              ))}
              <Correct event={e} onCorrected={onCorrected} />
              <span className="event-meta">{e.source} · {e.latency_ms} ms</span>
            </div>
          </li>
        );
      })}
    </ul>
  );
}
