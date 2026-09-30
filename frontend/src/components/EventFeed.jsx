import { useEffect, useState } from "react";
import { labelMeta } from "../config.js";

function ago(ts, now) {
  const s = Math.max(0, Math.round(now / 1000 - ts));
  if (s < 5) return "just now";
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  return `${Math.floor(s / 3600)}h ago`;
}

export default function EventFeed({ events, total, status }) {
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
        const low = e.confidence < 0.5;
        return (
          <li key={e.id} className="event" style={{ "--accent": m.color }}>
            <div className="event-top">
              <span className="badge" style={{ color: m.color, borderColor: m.color }}>{m.name}</span>
              <span className="conf" title={`Confidence ${pct}%`}>
                <span className="conf-track"><span className="conf-fill" style={{ width: `${pct}%`, background: m.color }} /></span>
                <span className={low ? "conf-low" : ""}>{pct}%{low ? " · low" : ""}</span>
              </span>
              <span className="event-meta">{ago(e.ts, now)}</span>
            </div>
            <p className="event-text">{e.text}</p>
            <div className="event-foot">
              {(e.top || []).slice(1).map((t) => (
                <span key={t.label} className="runner">{labelMeta(t.label).name} {Math.round(t.confidence * 100)}%</span>
              ))}
              <span className="event-meta">{e.source} · {e.latency_ms} ms</span>
            </div>
          </li>
        );
      })}
    </ul>
  );
}
