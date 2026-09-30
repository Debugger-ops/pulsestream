import Sparkline from "./Sparkline.jsx";

function Card({ label, value, hint, children }) {
  return (
    <div className="card">
      <div className="card-label">{label}</div>
      <div className="card-value">{value}</div>
      {hint && <div className="card-hint">{hint}</div>}
      {children}
    </div>
  );
}

const fmtUptime = (s) => {
  const m = Math.floor(s / 60);
  return m < 60 ? `${m}m ${s % 60}s` : `${Math.floor(m / 60)}h ${m % 60}m`;
};

export default function StatCards({ stats, series }) {
  const s = stats || {};
  return (
    <section className="cards" aria-label="Summary statistics">
      <Card label="Events classified" value={(s.total ?? 0).toLocaleString()} hint={s.uptime_sec != null ? `up ${fmtUptime(s.uptime_sec)}` : " "} />
      <Card label="Throughput" value={`${(s.throughput_per_sec ?? 0).toFixed(1)}/s`} hint="last 10s avg">
        <Sparkline points={series} />
      </Card>
      <Card label="Avg confidence" value={`${Math.round((s.avg_confidence ?? 0) * 100)}%`} hint="last 200 events" />
      <Card label="Inference latency" value={`${(s.avg_latency_ms ?? 0).toFixed(1)} ms`} hint="model only, avg" />
    </section>
  );
}
