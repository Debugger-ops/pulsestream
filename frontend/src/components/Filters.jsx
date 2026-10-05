export default function Filters({ minConf, setMinConf, query, setQuery, active, clearLabels, shown, total,
                                  reviewOnly, setReviewOnly, reviewCount, exportHref }) {
  return (
    <div className="filters">
      <input className="input" type="search" placeholder="Search text…" value={query}
             onChange={(e) => setQuery(e.target.value)} aria-label="Search events" />
      <label className="slider">
        <span>Min confidence <strong>{Math.round(minConf * 100)}%</strong></span>
        <input type="range" min="0" max="0.95" step="0.05" value={minConf}
               onChange={(e) => setMinConf(Number(e.target.value))} />
      </label>
      <button className={`btn ${reviewOnly ? "btn-on" : ""}`} aria-pressed={reviewOnly}
              onClick={() => setReviewOnly(!reviewOnly)}
              title="Low-confidence events that nobody has corrected yet">
        Needs review{reviewCount > 0 ? ` (${reviewCount})` : ""}
      </button>
      {active.length > 0 && <button className="btn btn-ghost" onClick={clearLabels}>Clear label filter ({active.length})</button>}
      <a className="btn btn-ghost" href={exportHref} download title="Download the events on the server, using the search, confidence and review filters">Export CSV</a>
      <span className="count">{shown} of {total}</span>
    </div>
  );
}
