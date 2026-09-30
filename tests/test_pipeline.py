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
