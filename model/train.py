"""
Trains the ticket classifier used by consumer/consumer.py.

    python3 model/train.py                        # TF-IDF + Logistic Regression (fast, default)
    python3 model/train.py --backend embeddings   # sentence-transformer embeddings + Logistic Regression
    python3 model/train.py --with-feedback        # also learn from corrections made in the dashboard

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


def load_feedback(path, valid_labels):
    """Corrections saved by the dashboard -> (texts, labels). Later corrections of the same text win."""
    latest = {}
    p = Path(path)
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
                if row["correct_label"] in valid_labels and row["text"].strip():
                    latest[row["text"].strip()] = row["correct_label"]
            except (ValueError, KeyError):
                continue
    return list(latest), list(latest.values())


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
    ap.add_argument("--with-feedback", action="store_true",
                    help="add human corrections from data/feedback.jsonl to the training data")
    ap.add_argument("--feedback", default=str(config.FEEDBACK_PATH))
    args = ap.parse_args()

    X, y = load_csv(args.data)
    Xh, yh = load_csv(args.holdout)
    n_feedback = 0
    if args.with_feedback:
        fx, fy = load_feedback(args.feedback, set(y))
        holdout_texts = {t.strip() for t in Xh}
        keep = [i for i, t in enumerate(fx) if t not in holdout_texts]   # never train on the holdout set
        X += [fx[i] for i in keep]
        y += [fy[i] for i in keep]
        n_feedback = len(keep)
    print(f"train: {len(X)} rows ({n_feedback} from feedback) | holdout: {len(Xh)} rows | backend: {args.backend}")

    pipe = build_pipeline(args.backend)
    cv = cross_val_score(pipe, X, y, cv=5, scoring="f1_macro")
    pipe.fit(X, y)

    pred = pipe.predict(Xh)
    labels = sorted(set(y))
    metrics = {
        "backend": args.backend,
        "train_rows": len(X),
        "feedback_rows": n_feedback,
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
