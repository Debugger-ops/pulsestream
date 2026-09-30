"""
FastAPI service.

* consumes `classified-events` from Kafka on a background thread (auto-retries)
* keeps the last N events in memory so new dashboards get history instantly
* broadcasts every event + a once-a-second stats snapshot over WebSocket /ws
* REST: /health, /events, /stats, /model

Demo mode (no Kafka needed, handy for UI work and screen recordings):
    DEMO_MODE=1 uvicorn backend.app:app --port 8000

WebSocket messages (server -> client), all JSON with a "type":
    {"type": "history", "events": [...], "stats": {...}}   once, on connect
    {"type": "event",   "event":  {...}}                   per classified event
    {"type": "stats",   "stats":  {...}}                   every second
"""
import asyncio
import csv
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

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config

DEMO_MODE = os.environ.get("DEMO_MODE") == "1"

history: deque = deque(maxlen=config.HISTORY_SIZE)
label_totals: Counter = Counter()
connected_clients: set = set()
started_at = time.time()
main_loop = None
kafka_status = {"connected": False, "error": None}


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
        await websocket.send_json({"type": "history", "events": list(history)[:50],
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


@app.get("/events")
async def events(limit: int = 50, label: str | None = None):
    items = [e for e in history if label is None or e["label"] == label]
    return items[: max(1, min(limit, config.HISTORY_SIZE))]


@app.get("/stats")
async def stats():
    return compute_stats()


@app.get("/model")
async def model_info():
    """Training metrics written by model/train.py (shown in the dashboard's About panel)."""
    if config.METRICS_PATH.exists():
        return json.loads(config.METRICS_PATH.read_text())
    return {"error": "no metrics yet - run `python3 model/train.py`"}
