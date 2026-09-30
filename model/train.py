"""
Trains the ticket classifier used by consumer/consumer.py.

    python3 model/train.py                        # TF-IDF + Logistic Regression (fast, default)
    python3 model/train.py --backend embeddings   # sentence-transformer embeddings + Logistic Regression

Evaluation is honest on purpose:
  * 5-fold cross-validation on data/tickets.csv (synthetic, phrasing-varied)
  * a hand-written HOLDOUT set (data/holdout.csv) of sentences the model never saw

Outputs: model/artifacts/classifier.pkl and model/artifacts/metrics.json
"""
import argparse
import csv
import json
import pickle
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
from sklearn.model_selection import cross_val_score
from sklearn.pipeline import Pipeline

import config


def load_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return [r["text"] for r in rows], [r["label"] for r in rows]


def build_pipeline(backend: str) -> Pipeline:
    if backend == "embeddings":
        from model.features import EmbeddingVectorizer
        features = ("embed", EmbeddingVectorizer())
    else:
        features = ("tfidf", TfidfVectorizer(max_features=5000, ngram_range=(1, 2), sublinear_tf=True))
    return Pipeline([features, ("clf", LogisticRegression(max_iter=2000, C=5.0))])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", choices=["tfidf", "embeddings"], default="tfidf")
    ap.add_argument("--data", default=str(config.DATA_FILE))
    ap.add_argument("--holdout", default=str(config.ROOT / "data" / "holdout.csv"))
    args = ap.parse_args()

    X, y = load_csv(args.data)
    Xh, yh = load_csv(args.holdout)
    print(f"train: {len(X)} rows | holdout: {len(Xh)} rows | backend: {args.backend}")

    pipe = build_pipeline(args.backend)
    cv = cross_val_score(pipe, X, y, cv=5, scoring="f1_macro")
    pipe.fit(X, y)

    pred = pipe.predict(Xh)
    labels = sorted(set(y))
    metrics = {
        "backend": args.backend,
        "train_rows": len(X),
        "holdout_rows": len(Xh),
        "labels": labels,
        "cv_macro_f1_mean": round(float(cv.mean()), 4),
        "cv_macro_f1_std": round(float(cv.std()), 4),
        "holdout_accuracy": round(float(accuracy_score(yh, pred)), 4),
        "holdout_macro_f1": round(float(f1_score(yh, pred, average="macro")), 4),
        "confusion_matrix": confusion_matrix(yh, pred, labels=labels).tolist(),
        "report": classification_report(yh, pred, output_dict=True, zero_division=0),
    }

    config.ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    with open(config.MODEL_PATH, "wb") as f:
        pickle.dump(pipe, f)
    with open(config.METRICS_PATH, "w") as f:
        json.dump(metrics, f, indent=2)

    print(f"5-fold CV macro-F1: {metrics['cv_macro_f1_mean']:.3f} +/- {metrics['cv_macro_f1_std']:.3f}")
    print(f"holdout accuracy:   {metrics['holdout_accuracy']:.3f}   macro-F1: {metrics['holdout_macro_f1']:.3f}")
    print(classification_report(yh, pred, zero_division=0))
    print(f"saved model   -> {config.MODEL_PATH}")
    print(f"saved metrics -> {config.METRICS_PATH}")


if __name__ == "__main__":
    main()
