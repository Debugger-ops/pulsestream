"""
Optional semantic features: sentence-transformer embeddings as a scikit-learn
transformer, so they drop into the same Pipeline as TF-IDF.

Only imported when you train with `--backend embeddings`
(needs: pip install -r requirements-embeddings.txt).
"""
from sklearn.base import BaseEstimator, TransformerMixin


class EmbeddingVectorizer(BaseEstimator, TransformerMixin):
    def __init__(self, model_name="sentence-transformers/all-MiniLM-L6-v2"):
        self.model_name = model_name
        self._model = None

    def _get(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name)
        return self._model

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        return self._get().encode(list(X), show_progress_bar=False, normalize_embeddings=True)

    def __getstate__(self):          # don't pickle the heavy model weights
        state = self.__dict__.copy()
        state["_model"] = None
        return state
