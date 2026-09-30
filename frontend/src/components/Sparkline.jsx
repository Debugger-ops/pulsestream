export default function Sparkline({ points }) {
  const w = 160, h = 34;
  if (!points || points.length < 2) return <div className="spark-empty">collecting…</div>;
  const max = Math.max(...points, 1) * 1.3;
  const step = w / (points.length - 1);
  const xy = points.map((p, i) => [i * step, h - 2 - (p / max) * (h - 6)]);
  const line = xy.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
  return (
    <svg className="spark" viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" role="img" aria-label="Throughput over the last minute">
      <path d={`${line} L${w},${h} L0,${h} Z`} fill="var(--c-praise)" opacity="0.15" />
      <path d={line} fill="none" stroke="var(--c-praise)" strokeWidth="1.8" strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}
