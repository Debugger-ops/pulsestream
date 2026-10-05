"""Fast tests that need no Kafka. Run: pytest -q"""
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import config


@pytest.fixture(scope="session", autouse=True)
def trained_model():
    subprocess.run([sys.executable, str(ROOT / "model" / "train.py")], check=True, capture_output=True)


def test_predict_shape_and_labels():
    from model.inference import predict
    label, conf, top = predict("I was charged twice for my subscription")
    assert label == "billing"
    assert 0 < conf <= 1
    assert len(top) == 3 and top[0]["label"] == label


def test_holdout_accuracy_floor():
    import json
    m = json.loads(config.METRICS_PATH.read_text())
    assert m["holdout_accuracy"] >= 0.75


def test_backend_rest_endpoints(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "1")
    import importlib, backend.app as app_mod
    importlib.reload(app_mod)
    with TestClient(app_mod.app) as client:
        assert client.get("/health").json()["status"] == "ok"
        assert "total" in client.get("/stats").json()
        assert "labels" in client.get("/model").json()
        with client.websocket_connect("/ws") as ws:
            assert ws.receive_json()["type"] == "history"


# ---------------------------------------------------------------- new features
@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("DEMO_MODE", "1")
    monkeypatch.setattr(config, "FEEDBACK_PATH", tmp_path / "feedback.jsonl")
    import importlib, backend.app as app_mod
    importlib.reload(app_mod)
    monkeypatch.setattr(app_mod, "demo_generator", lambda: None)   # no random events while we assert on history
    with TestClient(app_mod.app) as c:
        c.app_mod = app_mod
        yield c


def _seed(client, n=3):
    """Put known events in history (demo mode is also adding random ones in the background)."""
    import time
    m = client.app_mod
    m.history.clear()
    for i in range(n):
        m.history.appendleft({"id": f"seed{i}", "text": f"ticket number {i}", "ts": time.time(), "source": "test",
                              "label": "bug", "confidence": 0.9 if i else 0.3, "top": [], "latency_ms": 1.0,
                              "classified_ts": time.time()})


def test_classify_endpoint(client):
    r = client.post("/classify", json={"text": "I was charged twice for my subscription"})
    assert r.status_code == 200
    body = r.json()
    assert body["label"] == "billing" and len(body["top"]) == 3 and "latency_ms" in body
    assert client.post("/classify", json={"text": "   "}).status_code == 400
    assert client.post("/classify", json={"text": "x" * (config.MAX_TEXT_LEN + 1)}).status_code == 413


def test_events_filters_and_paging(client):
    _seed(client, 5)
    assert len(client.get("/events?limit=2").json()) == 2
    assert [e["id"] for e in client.get("/events?limit=2&offset=2").json()] == ["seed2", "seed1"]
    assert [e["text"] for e in client.get("/events?q=NUMBER 3").json()] == ["ticket number 3"]
    assert [e["id"] for e in client.get("/events?needs_review=true").json()] == ["seed0"]
    assert client.get("/events?min_confidence=2").status_code == 422


def test_feedback_roundtrip_and_persistence(client):
    import json
    _seed(client, 2)
    assert client.post("/feedback", json={"event_id": "seed1", "correct_label": "nonsense"}).status_code == 422
    assert client.post("/feedback", json={"event_id": "gone", "correct_label": "billing"}).status_code == 404
    r = client.post("/feedback", json={"event_id": "seed0", "correct_label": "billing"})
    assert r.status_code == 200 and r.json()["total_corrections"] == 1
    # corrected events leave the review queue and carry the corrected label
    assert client.get("/events?needs_review=true").json() == []
    assert client.get("/events?corrected=true").json()[0]["corrected_label"] == "billing"
    summary = client.get("/feedback").json()
    assert summary["total"] == 1 and summary["model_was_wrong"] == 1
    saved = json.loads(config.FEEDBACK_PATH.read_text().splitlines()[0])
    assert saved["text"] == "ticket number 0" and saved["correct_label"] == "billing"
    client.app_mod.corrections.clear()
    client.app_mod.load_feedback_file()                  # what happens on restart
    assert client.app_mod.corrections == {"seed0": "billing"}


def test_feedback_is_broadcast_over_websocket(client):
    _seed(client, 1)
    with client.websocket_connect("/ws") as ws:
        assert ws.receive_json()["type"] == "history"
        client.post("/feedback", json={"event_id": "seed0", "correct_label": "praise"})
        for _ in range(20):                              # stats ticks / demo events may arrive first
            msg = ws.receive_json()
            if msg["type"] == "feedback":
                assert msg == {"type": "feedback", "event_id": "seed0", "corrected_label": "praise"}
                break
        else:
            pytest.fail("no feedback message received")


def test_export_csv(client):
    import csv, io
    _seed(client, 3)
    r = client.get("/events/export.csv?needs_review=true")
    assert r.headers["content-type"].startswith("text/csv")
    rows = list(csv.DictReader(io.StringIO(r.text)))
    assert [row["id"] for row in rows] == ["seed0"] and rows[0]["label"] == "bug"


def test_prometheus_metrics(client):
    _seed(client, 2)
    text = client.get("/metrics").text
    assert "# TYPE pulsestream_events_total counter" in text
    assert "pulsestream_low_confidence_recent 1" in text
    assert "pulsestream_corrections_total 0" in text


def test_train_with_feedback_adds_rows_but_never_holdout(tmp_path):
    import json
    from model.train import load_feedback
    fb = tmp_path / "fb.jsonl"
    fb.write_text("\n".join(json.dumps(r) for r in [
        {"text": "my invoice is wrong", "correct_label": "billing"},
        {"text": "my invoice is wrong", "correct_label": "bug"},          # later correction wins
        {"text": "weird", "correct_label": "not-a-label"},                # ignored
    ]) + "\nnot json\n")                                                  # corrupt lines are skipped
    texts, labels = load_feedback(fb, {"billing", "bug"})
    assert (texts, labels) == (["my invoice is wrong"], ["bug"])
