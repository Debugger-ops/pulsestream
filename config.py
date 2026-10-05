"""
Shared settings for every PulseStream service.

All values can be overridden with environment variables, so the same code
runs locally, in Docker, or on a server without edits.
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent

KAFKA_BROKER = os.environ.get("KAFKA_BROKER", "localhost:9092")
RAW_TOPIC = os.environ.get("RAW_TOPIC", "raw-events")
CLASSIFIED_TOPIC = os.environ.get("CLASSIFIED_TOPIC", "classified-events")

DATA_FILE = Path(os.environ.get("DATA_FILE", ROOT / "data" / "tickets.csv"))
ARTIFACT_DIR = Path(os.environ.get("ARTIFACT_DIR", ROOT / "model" / "artifacts"))
MODEL_PATH = ARTIFACT_DIR / "classifier.pkl"
METRICS_PATH = ARTIFACT_DIR / "metrics.json"
# Human corrections made in the dashboard (one JSON object per line); used by `train.py --with-feedback`
FEEDBACK_PATH = Path(os.environ.get("FEEDBACK_FILE", ROOT / "data" / "feedback.jsonl"))

# Backend
ALLOWED_ORIGINS = os.environ.get(
    "ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
).split(",")
HISTORY_SIZE = int(os.environ.get("HISTORY_SIZE", "200"))

# Events below this confidence are flagged "low" and land in the dashboard's review queue
LOW_CONFIDENCE = float(os.environ.get("LOW_CONFIDENCE", "0.5"))
MAX_TEXT_LEN = int(os.environ.get("MAX_TEXT_LEN", "2000"))
