"""
Loads the trained classifier and exposes predict().
"""
import pickle
import sys
from functools import lru_cache
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config


@lru_cache(maxsize=1)
def _load_model():
    if not config.MODEL_PATH.exists():
        raise FileNotFoundError(
            f"No trained model at {config.MODEL_PATH}. Run `python3 model/train.py` first."
        )
    with open(config.MODEL_PATH, "rb") as f:
        return pickle.load(f)


def predict(text: str, top_k: int = 3):
    """Returns (label, confidence, top) for one piece of text.

    `top` is a list of {"label", "confidence"} for the top_k classes, so the
    dashboard can show runner-up guesses.
    """
    model = _load_model()
    proba = model.predict_proba([text])[0]
    classes = model.classes_
    ranked = sorted(zip(classes, proba), key=lambda p: p[1], reverse=True)
    top = [{"label": str(l), "confidence": round(float(p), 4)} for l, p in ranked[:top_k]]
    return top[0]["label"], top[0]["confidence"], top
