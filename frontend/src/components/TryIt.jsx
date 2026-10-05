import { useState } from "react";
import { classifyText } from "../api.js";
import { labelMeta } from "../config.js";

export default function TryIt() {
  const [text, setText] = useState("");
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const submit = async (ev) => {
    ev.preventDefault();
    if (!text.trim()) return;
    setBusy(true); setError(null);
    try { setResult(await classifyText(text)); }
    catch (e) { setResult(null); setError(e.message); }
    finally { setBusy(false); }
  };

  const m = result && labelMeta(result.label);
  return (
    <section className="panel" aria-label="Try the classifier">
      <h2>Try it</h2>
      <p className="panel-sub">Classify any text on demand. It isn’t added to the live feed.</p>
      <form onSubmit={submit} className="tryit">
        <textarea className="input" rows="3" maxLength={2000} placeholder="e.g. I was charged twice this month"
                  value={text} onChange={(e) => setText(e.target.value)}
                  onKeyDown={(e) => { if ((e.metaKey || e.ctrlKey) && e.key === "Enter") submit(e); }}
                  aria-label="Text to classify" />
        <button className="btn" disabled={busy || !text.trim()}>{busy ? "Classifying…" : "Classify"}</button>
      </form>
      {error && <p className="conf-low" role="alert">{error}</p>}
      {result && (
        <div className="tryit-result" role="status">
          <span className="badge" style={{ color: m.color, borderColor: m.color }}>{m.name}</span>
          <strong>{Math.round(result.confidence * 100)}%</strong>
          {result.low_confidence && <span className="conf-low">· low confidence</span>}
          <span className="event-meta">{result.latency_ms} ms</span>
          <div className="event-foot">
            {result.top.slice(1).map((t) => (
              <span key={t.label} className="runner">{labelMeta(t.label).name} {Math.round(t.confidence * 100)}%</span>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
