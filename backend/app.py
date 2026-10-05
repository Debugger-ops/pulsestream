"""
FastAPI service.

* consumes `classified-events` from Kafka on a background thread (auto-retries)
* keeps the last N events in memory so new dashboards get history instantly
* broadcasts every event + a once-a-second stats snapshot over WebSocket /ws
* REST: /health, /events (paged + filters), /events/export.csv, /stats, /model,
        POST /classify, POST /feedback, GET /feedback, POST /model/reload, /metrics (Prometheus)

Demo mode (no Kafka needed, handy for UI work and screen recordings):
    DEMO_MODE=1 uvicorn backend.app:app --port 8000

WebSocket messages (server -> client), all JSON with a "type":
    {"type": "history", "events": [...], "stats": {...}}   once, on connect
    {"type": "event",   "event":  {...}}                   per classified event
    {"type": "stats",   "stats":  {...}}                   every second
    {"type": "feedback","event_id": "...", "corrected_label": "..."}   when anyone corrects a label
"""
import asyncio
import csv
import io
import json
import os
import random
import sys
import threading
import time
import uuid
from collections import Counter, deque
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Response, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config

DEMO_MODE = os.environ.get("DEMO_MODE") == "1"

history: deque = deque(maxlen=config.HISTORY_SIZE)
label_totals: Counter = Counter()
connected_clients: set = set()
started_at = time.time()
main_loop = None
kafka_status = {"connected": False, "error": None}
corrections: dict = {}                  # event id -> human-corrected label
feedback_lock = threading.Lock()
adhoc_classified = 0                    # how many POST /classify calls were served


def load_feedback_file():
    """Restore corrections saved by earlier runs so they survive a restart."""
    corrections.clear()
    if config.FEEDBACK_PATH.exists():
        for line in config.FEEDBACK_PATH.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
                corrections[row["event_id"]] = row["correct_label"]
            except (ValueError, KeyError):
                continue            # ignore a corrupt line rather than failing startup


def with_correction(event: dict) -> dict:
    return {**event, "corrected_label": corrections[event["id"]]} if event.get("id") in corrections else event


def valid_labels() -> list:
    from model.inference import _load_model
    return [str(c) for c in _load_model().classes_]


# ------------------------------------------------------------------ stats
def compute_stats() -> dict:
    now = time.time()
    recent = [e for e in history if now - e.get("classified_ts", now) <= 10]
    total = sum(label_totals.values())
    confs = [e["confidence"] for e in history]
    lats = [e["latency_ms"] for e in history if "latency_ms" in e]
    return {
        "total": total,
        "label_totals": dict(label_totals),
        "throughput_per_sec": round(len(recent) / 10, 2),
        "avg_confidence": round(sum(confs) / len(confs), 4) if confs else 0,
        "avg_latency_ms": round(sum(lats) / len(lats), 2) if lats else 0,
        "uptime_sec": int(now - started_at),
        "kafka_connected": kafka_status["connected"],
        "demo_mode": DEMO_MODE,
    }


# -------------------------------------------------------------- broadcast
async def broadcast(message: dict):
    dead = []
    for ws in list(connected_clients):
        try:
            await ws.send_json(message)
        except Exception:
            dead.append(ws)
    for ws in dead:
        connected_clients.discard(ws)


async def ingest(event: dict):
    event = with_correction(event)
    history.appendleft(event)
    label_totals[event["label"]] += 1
    await broadcast({"type": "event", "event": event})


def submit_from_thread(event: dict):
    if main_loop is not None:
        asyncio.run_coroutine_threadsafe(ingest(event), main_loop)


# ------------------------------------------------------------ event sources
def kafka_listener():
    from kafka_utils import make_consumer
    while True:
        try:
            consumer = make_consumer(config.CLASSIFIED_TOPIC, "dashboard-backend", "backend")
            kafka_status.update(connected=True, error=None)
            for msg in consumer:
                if isinstance(msg.value, dict) and "label" in msg.value:
                    submit_from_thread(msg.value)
        except SystemExit as e:                     # kafka_utils gave up; try again later
            kafka_status.update(connected=False, error=str(e))
        except Exception as e:
            kafka_status.update(connected=False, error=str(e))
        time.sleep(5)


def demo_generator():
    """Classifies sample sentences locally and feeds them straight to the dashboard."""
    from model.inference import predict
    with open(config.ROOT / "data" / "holdout.csv", newline="", encoding="utf-8") as f:
        texts = [r["text"] for r in csv.DictReader(f)]
    kafka_status.update(connected=False, error="demo mode (Kafka bypassed)")
    while True:
        text = random.choice(texts)
        t0 = time.perf_counter()
        label, conf, top = predict(text)
        submit_from_thread({
            "id": uuid.uuid4().hex[:12], "text": text, "ts": time.time(), "source": "demo",
            "label": label, "confidence": conf, "top": top,
            "latency_ms": round((time.perf_counter() - t0) * 1000, 2),
            "classified_ts": time.time(),
        })
        time.sleep(random.uniform(0.4, 1.6))


async def stats_ticker():
    while True:
        await asyncio.sleep(1)
        if connected_clients:
            await broadcast({"type": "stats", "stats": compute_stats()})


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global main_loop
    main_loop = asyncio.get_running_loop()
    load_feedback_file()
    target = demo_generator if DEMO_MODE else kafka_listener
    threading.Thread(target=target, daemon=True).start()
    ticker = asyncio.create_task(stats_ticker())
    yield
    ticker.cancel()


app = FastAPI(title="PulseStream", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=config.ALLOWED_ORIGINS,
                   allow_methods=["*"], allow_headers=["*"])


# -------------------------------------------------------------------- routes
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.add(websocket)
    try:
        await websocket.send_json({"type": "history", "events": [with_correction(e) for e in list(history)[:50]],
                                   "stats": compute_stats()})
        while True:
            await websocket.receive_text()          # keeps the socket open; client sends pings
    except WebSocketDisconnect:
        pass
    finally:
        connected_clients.discard(websocket)


@app.get("/health")
async def health():
    return {"status": "ok", "connected_clients": len(connected_clients), **kafka_status}


def filter_events(label, q, min_confidence, needs_review, corrected):
    q = (q or "").strip().lower()
    out = []
    for e in history:
        e = with_correction(e)
        if label and e["label"] != label:
            continue
        if q and q not in e["text"].lower():
            continue
        if e["confidence"] < min_confidence:
            continue
        if needs_review and not (e["confidence"] < config.LOW_CONFIDENCE and "corrected_label" not in e):
            continue
        if corrected is not None and ("corrected_label" in e) != corrected:
            continue
        out.append(e)
    return out


@app.get("/events")
async def events(limit: int = Query(50, ge=1), offset: int = Query(0, ge=0), label: str | None = None,
                 q: str | None = None, min_confidence: float = Query(0, ge=0, le=1),
                 needs_review: bool = False, corrected: bool | None = None):
    """Newest first. Filters: label, q (text search), min_confidence, needs_review
    (low confidence and not yet corrected), corrected (true/false)."""
    items = filter_events(label, q, min_confidence, needs_review, corrected)
    return items[offset: offset + min(limit, config.HISTORY_SIZE)]


@app.get("/events/export.csv")
async def export_events(label: str | None = None, q: str | None = None,
                        min_confidence: float = Query(0, ge=0, le=1),
                        needs_review: bool = False, corrected: bool | None = None):
    """Download the (filtered) in-memory history as CSV."""
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "time_iso", "source", "text", "label", "confidence",
                "corrected_label", "latency_ms"])
    for e in filter_events(label, q, min_confidence, needs_review, corrected):
        w.writerow([e["id"], time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(e.get("ts", 0))),
                    e.get("source", ""), e["text"], e["label"], e["confidence"],
                    e.get("corrected_label", ""), e.get("latency_ms", "")])
    return Response(buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=pulsestream-events.csv"})


class ClassifyRequest(BaseModel):
    text: str


@app.post("/classify")
def classify(req: ClassifyRequest):
    """Classify one piece of text on demand (the dashboard's "Try it" box). Not added to the live feed."""
    global adhoc_classified
    text = req.text.strip()
    if not text:
        raise HTTPException(400, "text must not be empty")
    if len(text) > config.MAX_TEXT_LEN:
        raise HTTPException(413, f"text is longer than {config.MAX_TEXT_LEN} characters")
    from model.inference import predict
    t0 = time.perf_counter()
    label, conf, top = predict(text)
    adhoc_classified += 1
    return {"text": text, "label": label, "confidence": conf, "top": top,
            "latency_ms": round((time.perf_counter() - t0) * 1000, 2),
            "low_confidence": conf < config.LOW_CONFIDENCE}


class FeedbackRequest(BaseModel):
    event_id: str
    correct_label: str
    text: str | None = None      # only needed if the event already fell out of history


@app.post("/feedback")
async def submit_feedback(req: FeedbackRequest):
    """Record a human correction. Saved to data/feedback.jsonl; `model/train.py --with-feedback` learns from it."""
    labels = valid_labels()
    if req.correct_label not in labels:
        raise HTTPException(422, f"correct_label must be one of {labels}")
    event = next((e for e in history if e.get("id") == req.event_id), None)
    text = event["text"] if event else (req.text or "").strip()
    if not text:
        raise HTTPException(404, "unknown event_id and no text supplied")
    row = {"event_id": req.event_id, "text": text, "correct_label": req.correct_label,
           "predicted_label": event["label"] if event else None,
           "confidence": event["confidence"] if event else None, "ts": time.time()}
    with feedback_lock:
        config.FEEDBACK_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(config.FEEDBACK_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")
        corrections[req.event_id] = req.correct_label
    await broadcast({"type": "feedback", "event_id": req.event_id, "corrected_label": req.correct_label})
    return {"ok": True, "total_corrections": len(corrections)}


@app.get("/feedback")
async def feedback_summary():
    """How many corrections exist and how many of them changed the model's guess."""
    rows = []
    if config.FEEDBACK_PATH.exists():
        for line in config.FEEDBACK_PATH.read_text(encoding="utf-8").splitlines():
            try:
                rows.append(json.loads(line))
            except ValueError:
                continue
    wrong = sum(1 for r in rows if r.get("predicted_label") and r["predicted_label"] != r["correct_label"])
    return {"total": len(rows), "model_was_wrong": wrong,
            "by_label": dict(Counter(r["correct_label"] for r in rows))}


@app.get("/stats")
async def stats():
    return compute_stats()


@app.get("/model")
async def model_info():
    """Training metrics written by model/train.py (shown in the dashboard's About panel)."""
    if config.METRICS_PATH.exists():
        return json.loads(config.METRICS_PATH.read_text())
    return {"error": "no metrics yet - run `python3 model/train.py`"}


@app.post("/model/reload")
async def reload_model():
    """Pick up a freshly trained model.pkl without restarting (run `train.py --with-feedback` first)."""
    from model.inference import _load_model
    _load_model.cache_clear()
    _load_model()
    return {"ok": True, "labels": valid_labels()}


@app.get("/metrics")
async def prometheus_metrics():
    """Prometheus text exposition format - scrape with `scrape_configs: [{targets: ['localhost:8000']}]`."""
    st = compute_stats()
    lines = [
        "# HELP pulsestream_events_total Events classified since the backend started.",
        "# TYPE pulsestream_events_total counter",
        f"pulsestream_events_total {st['total']}",
        "# HELP pulsestream_events_by_label_total Events classified, by predicted label.",
        "# TYPE pulsestream_events_by_label_total counter",
        *[f'pulsestream_events_by_label_total{{label="{l}"}} {n}' for l, n in sorted(label_totals.items())],
        "# HELP pulsestream_throughput_per_second Events/second over the last 10 seconds.",
        "# TYPE pulsestream_throughput_per_second gauge",
        f"pulsestream_throughput_per_second {st['throughput_per_sec']}",
        "# HELP pulsestream_avg_confidence Mean confidence of recent events (0-1).",
        "# TYPE pulsestream_avg_confidence gauge",
        f"pulsestream_avg_confidence {st['avg_confidence']}",
        "# HELP pulsestream_avg_latency_ms Mean model latency of recent events.",
        "# TYPE pulsestream_avg_latency_ms gauge",
        f"pulsestream_avg_latency_ms {st['avg_latency_ms']}",
        "# HELP pulsestream_low_confidence_recent Recent events under the low-confidence threshold.",
        "# TYPE pulsestream_low_confidence_recent gauge",
        f"pulsestream_low_confidence_recent {sum(1 for e in history if e['confidence'] < config.LOW_CONFIDENCE)}",
        "# HELP pulsestream_corrections_total Human label corrections recorded.",
        "# TYPE pulsestream_corrections_total gauge",
        f"pulsestream_corrections_total {len(corrections)}",
        "# HELP pulsestream_adhoc_classifications_total Calls served by POST /classify.",
        "# TYPE pulsestream_adhoc_classifications_total counter",
        f"pulsestream_adhoc_classifications_total {adhoc_classified}",
        "# HELP pulsestream_websocket_clients Connected dashboards.",
        "# TYPE pulsestream_websocket_clients gauge",
        f"pulsestream_websocket_clients {len(connected_clients)}",
        "# HELP pulsestream_kafka_connected 1 if the backend is consuming from Kafka.",
        "# TYPE pulsestream_kafka_connected gauge",
        f"pulsestream_kafka_connected {int(kafka_status['connected'])}",
        "# HELP pulsestream_uptime_seconds Backend uptime.",
        "# TYPE pulsestream_uptime_seconds gauge",
        f"pulsestream_uptime_seconds {st['uptime_sec']}",
    ]
    return Response("\n".join(lines) + "\n", media_type="text/plain; version=0.0.4")
