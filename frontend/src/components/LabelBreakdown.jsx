import { LABELS, labelMeta } from "../config.js";

export default function LabelBreakdown({ totals, active, onToggle }) {
  const counts = Object.keys(LABELS).map((l) => [l, totals?.[l] || 0]);
  const extra = Object.keys(totals || {}).filter((l) => !(l in LABELS)).map((l) => [l, totals[l]]);
  const rows = [...counts, ...extra];
  const sum = rows.reduce((a, [, n]) => a + n, 0) || 1;

  return (
    <section className="panel" aria-label="Label distribution">
      <h2>Distribution</h2>
      <p className="panel-sub">Click a label to filter the feed</p>
      <ul className="bars">
        {rows.map(([label, n]) => {
          const m = labelMeta(label);
          const pct = (n / sum) * 100;
          const on = active.includes(label);
          return (
            <li key={label}>
              <button className={`bar-row ${on ? "is-on" : ""}`} onClick={() => onToggle(label)} aria-pressed={on}>
                <span className="bar-name">{m.name}</span>
                <span className="bar-track"><span className="bar-fill" style={{ width: `${pct}%`, background: m.color }} /></span>
                <span className="bar-num">{n} <em>{pct.toFixed(0)}%</em></span>
              </button>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
