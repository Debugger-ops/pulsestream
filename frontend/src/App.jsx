import { useMemo, useState } from "react";
import { useEventStream } from "./hooks/useEventStream.js";
import Header from "./components/Header.jsx";
import StatCards from "./components/StatCards.jsx";
import LabelBreakdown from "./components/LabelBreakdown.jsx";
import Filters from "./components/Filters.jsx";
import EventFeed from "./components/EventFeed.jsx";
import ModelPanel from "./components/ModelPanel.jsx";
import TryIt from "./components/TryIt.jsx";
import { exportUrl } from "./api.js";
import { LOW_CONFIDENCE } from "./config.js";

export default function App() {
  const { events, stats, series, status, retryIn, reconnectNow, clear, corrections, markCorrected } = useEventStream();
  const [activeLabels, setActiveLabels] = useState([]);
  const [minConf, setMinConf] = useState(0);
  const [query, setQuery] = useState("");
  const [paused, setPaused] = useState(false);
  const [frozen, setFrozen] = useState([]);
  const [reviewOnly, setReviewOnly] = useState(false);

  // merge human corrections into events (also covers the frozen copy while paused)
  const source = useMemo(
    () => (paused ? frozen : events).map((e) => (corrections[e.id] ? { ...e, corrected_label: corrections[e.id] } : e)),
    [paused, frozen, events, corrections]
  );
  const needsReview = (e) => e.confidence < LOW_CONFIDENCE && !e.corrected_label;
  const reviewCount = useMemo(() => source.filter(needsReview).length, [source]);

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    return source.filter((e) =>
      (activeLabels.length === 0 || activeLabels.includes(e.label)) &&
      e.confidence >= minConf &&
      (!reviewOnly || needsReview(e)) &&
      (!q || e.text.toLowerCase().includes(q))
    );
  }, [source, activeLabels, minConf, query, reviewOnly]);

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
                   shown={visible.length} total={source.length}
                   reviewOnly={reviewOnly} setReviewOnly={setReviewOnly} reviewCount={reviewCount}
                   exportHref={exportUrl({ q: query.trim(), min_confidence: minConf || "", needs_review: reviewOnly })} />
          <EventFeed events={visible} total={source.length} status={status} onCorrected={markCorrected} />
        </section>

        <aside className="side">
          <TryIt />
          <LabelBreakdown totals={stats?.label_totals} active={activeLabels} onToggle={toggleLabel} />
          <ModelPanel />
        </aside>
      </main>
    </div>
  );
}
