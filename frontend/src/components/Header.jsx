const TEXT = {
  live: "Live",
  connecting: "Connecting…",
  reconnecting: "Reconnecting…",
};

export default function Header({ status, retryIn, stats, onReconnect, paused, onTogglePause, onClear }) {
  return (
    <header className="header">
      <div className="brand">
        <svg width="28" height="28" viewBox="0 0 32 32" aria-hidden="true">
          <rect width="32" height="32" rx="8" fill="var(--panel-2)" />
          <path d="M3 17h6l3-9 5 17 4-11 2 3h6" fill="none" stroke="var(--c-praise)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        <div>
          <h1>PulseStream</h1>
          <p>Real-time event classifier</p>
        </div>
      </div>

      <div className="header-actions">
        {stats?.demo_mode && <span className="pill pill-demo" title="Backend is generating sample events, Kafka is bypassed">Demo mode</span>}
        {stats && !stats.demo_mode && (
          <span className={`pill ${stats.kafka_connected ? "pill-ok" : "pill-warn"}`}>
            Kafka {stats.kafka_connected ? "connected" : "waiting"}
          </span>
        )}
        <span className={`pill pill-${status}`} role="status" aria-live="polite">
          <span className="dot" />
          {TEXT[status]}
          {status === "reconnecting" && retryIn ? ` (${retryIn}s)` : ""}
        </span>
        {status === "reconnecting" && (
          <button className="btn" onClick={onReconnect}>Retry now</button>
        )}
        <button className="btn" onClick={onTogglePause} aria-pressed={paused}>
          {paused ? "▶ Resume feed" : "❚❚ Pause feed"}
        </button>
        <button className="btn btn-ghost" onClick={onClear}>Clear</button>
      </div>
    </header>
  );
}
