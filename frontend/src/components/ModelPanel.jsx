import { useEffect, useState } from "react";
import { API_URL, labelMeta } from "../config.js";

export default function ModelPanel() {
  const [m, setM] = useState(null);
  useEffect(() => {
    fetch(`${API_URL}/model`).then((r) => r.json()).then(setM).catch(() => setM({ error: "backend unreachable" }));
  }, []);

  if (!m) return null;
  if (m.error) return <section className="panel"><h2>Model</h2><p className="panel-sub">{m.error}</p></section>;

  return (
    <section className="panel" aria-label="Model details">
      <h2>Model</h2>
      <p className="panel-sub">{m.backend === "embeddings" ? "Sentence embeddings" : "TF-IDF"} + Logistic Regression</p>
      <dl className="kv">
        <div><dt>Holdout accuracy</dt><dd>{Math.round(m.holdout_accuracy * 100)}%</dd></div>
        <div><dt>Holdout macro-F1</dt><dd>{m.holdout_macro_f1.toFixed(2)}</dd></div>
        <div><dt>Train / holdout rows</dt><dd>{m.train_rows} / {m.holdout_rows}</dd></div>
      </dl>
      <table className="mini">
        <thead><tr><th>Class</th><th>Prec</th><th>Recall</th><th>F1</th></tr></thead>
        <tbody>
          {m.labels.map((l) => {
            const r = m.report[l];
            return <tr key={l}><td>{labelMeta(l).name}</td><td>{r.precision.toFixed(2)}</td><td>{r.recall.toFixed(2)}</td><td>{r["f1-score"].toFixed(2)}</td></tr>;
          })}
        </tbody>
      </table>
    </section>
  );
}
