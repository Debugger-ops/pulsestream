import { useMemo, useState } from "react";
import { useEventStream } from "./hooks/useEventStream.js";
import Header from "./components/Header.jsx";
import StatCards from "./components/StatCards.jsx";
import LabelBreakdown from "./components/LabelBreakdown.jsx";
import Filters from "./components/Filters.jsx";
import EventFeed from "./components/EventFeed.jsx";
import ModelPanel from "./components/ModelPanel.jsx";

export default function App() {
  const { events, stats, series, status, retryIn, reconnectNow, clear } = useEventStream();
  const [activeLabels, setActiveLabels] = useState([]);
  const [minConf, setMinConf] = useState(0);
  const [query, setQuery] = useState("");
  const [paused, setPaused] = useState(false);
  const [frozen, setFrozen] = useState([]);

  const source = paused ? frozen : events;

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    return source.filter((e) =>
      (activeLabels.length === 0 || activeLabels.includes(e.label)) &&
      e.confidence >= minConf &&
      (!q || e.text.toLowerCase().includes(q))
    );
  }, [source, activeLabels, minConf, query]);

  const toggleLabel = (l) =>
    setActiveLabels((cur) => (cur.includes(l) ? cur.filter((x) => x !== l) : [...cur, l]));

  const togglePause = () => {
    if (!paused) setFrozen(events);
    setPaused((p) => !p);
  };

  return (
    <div className="app">
      <Header status={status} retryIn={retryIn} stats={stats} onReconnect={reconnectNow}
              paused={paused} onTogglePause={togglePause} onClear={clear} />
      <StatCards stats={stats} series={series} />

      <main className="grid">
        <section className="panel feed-panel" aria-label="Live event feed">
          <div className="panel-head">
            <h2>Live feed {paused && <span className="pill pill-warn">paused</span>}</h2>
          </div>
          <Filters minConf={minConf} setMinConf={setMinConf} query={query} setQuery={setQuery}
                   active={activeLabels} clearLabels={() => setActiveLabels([])}
                   shown={visible.length} total={source.length} />
          <EventFeed events={visible} total={source.length} status={status} />
        </section>

        <aside className="side">
          <LabelBreakdown totals={stats?.label_totals} active={activeLabels} onToggle={toggleLabel} />
          <ModelPanel />
        </aside>
      </main>
    </div>
  );
}
