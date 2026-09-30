"""Generates notebooks/01_model_experiments.ipynb (run once; then edit the notebook freely)."""
import nbformat as nbf
from pathlib import Path

nb = nbf.v4.new_notebook()
md = lambda s: nbf.v4.new_markdown_cell(s.strip())
code = lambda s: nbf.v4.new_code_cell(s.strip())

nb.cells = [
md("""
# PulseStream — model experiments
Explores the ticket data, evaluates the classifier honestly, and looks at where it fails.
Run from the `notebooks/` folder (or anywhere — paths are resolved from the project root).
"""),
code("""
import sys
from pathlib import Path
import pandas as pd, numpy as np
import matplotlib.pyplot as plt
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.model_selection import cross_val_score
from sklearn.metrics import classification_report, ConfusionMatrixDisplay, accuracy_score, f1_score

ROOT = Path.cwd() if (Path.cwd() / "data").exists() else Path.cwd().parent
train = pd.read_csv(ROOT / "data" / "tickets.csv")
hold = pd.read_csv(ROOT / "data" / "holdout.csv")
print(len(train), "train rows,", len(hold), "holdout rows")
train.sample(5, random_state=1)
"""),
md("## 1. Data: label balance and text length"),
code("""
fig, ax = plt.subplots(1, 2, figsize=(11, 3.5))
train.label.value_counts().plot.barh(ax=ax[0], color="#60a5fa"); ax[0].set_title("Training rows per label")
train.text.str.split().str.len().plot.hist(ax=ax[1], bins=15, color="#34d399"); ax[1].set_title("Words per ticket")
plt.tight_layout(); plt.show()
"""),
md("""
## 2. Baseline: TF-IDF + Logistic Regression
Cross-validation on the training set **overstates** quality, because the synthetic tickets reuse each sentence with
small phrasing changes. The hand-written holdout set is the honest number.
"""),
code("""
def make(C=5.0, ngram=(1, 2)):
    return Pipeline([("tfidf", TfidfVectorizer(ngram_range=ngram, sublinear_tf=True)),
                     ("clf", LogisticRegression(C=C, max_iter=2000))])

pipe = make().fit(train.text, train.label)
pred = pipe.predict(hold.text)
print("CV macro-F1 (inflated):", round(cross_val_score(make(), train.text, train.label, cv=5, scoring="f1_macro").mean(), 3))
print("Holdout accuracy:", round(accuracy_score(hold.label, pred), 3), "| macro-F1:", round(f1_score(hold.label, pred, average="macro"), 3))
print(classification_report(hold.label, pred, zero_division=0))
"""),
code("""
fig, ax = plt.subplots(figsize=(6, 5))
ConfusionMatrixDisplay.from_predictions(hold.label, pred, ax=ax, xticks_rotation=45, cmap="Blues", colorbar=False)
ax.set_title("Holdout confusion matrix"); plt.tight_layout(); plt.show()
"""),
md("## 3. Error analysis — what does it get wrong, and how sure was it?"),
code("""
proba = pipe.predict_proba(hold.text)
out = hold.assign(pred=pred, confidence=proba.max(axis=1).round(2))
out[out.label != out.pred].sort_values("confidence", ascending=False)
"""),
md("Confidence vs correctness — a useful dashboard threshold is where wrong answers start to dominate."),
code("""
out["correct"] = out.label == out.pred
print(out.groupby(pd.cut(out.confidence, [0, .3, .5, .7, 1.0]), observed=True).correct.agg(["mean", "count"]).round(2))
"""),
md("## 4. Quick hyper-parameter sweep (scored on the holdout set)"),
code("""
rows = []
for C in [0.5, 1, 5, 20, 100]:
    for ngram in [(1, 1), (1, 2)]:
        p = make(C, ngram).fit(train.text, train.label).predict(hold.text)
        rows.append({"C": C, "ngram": ngram, "holdout_acc": accuracy_score(hold.label, p), "macro_f1": f1_score(hold.label, p, average="macro")})
pd.DataFrame(rows).sort_values("macro_f1", ascending=False).round(3)
"""),
md("""
## 5. Optional: sentence embeddings
Needs `pip install -r requirements-embeddings.txt` (downloads a model, ~100 MB + PyTorch). Skipped automatically if not installed.
"""),
code("""
try:
    sys.path.insert(0, str(ROOT))
    from model.features import EmbeddingVectorizer
    emb = Pipeline([("embed", EmbeddingVectorizer()), ("clf", LogisticRegression(C=5, max_iter=2000))])
    p = emb.fit(train.text, train.label).predict(hold.text)
    print("Embeddings holdout accuracy:", round(accuracy_score(hold.label, p), 3), "| macro-F1:", round(f1_score(hold.label, p, average="macro"), 3))
except ImportError:
    print("sentence-transformers not installed - skipping")
"""),
md("""
## 6. Takeaways
- Wording unseen at training time drags TF-IDF down; `billing` is the weakest class.
- Low-confidence predictions are much less reliable — the dashboard's "low" flag (<50%) is justified.
- Next: real labelled tickets, and compare against the embeddings model above.
"""),
]
nb.metadata["kernelspec"] = {"display_name": "Python 3", "language": "python", "name": "python3"}
out = Path(__file__).with_name("01_model_experiments.ipynb")
nbf.write(nb, out); print("wrote", out)
