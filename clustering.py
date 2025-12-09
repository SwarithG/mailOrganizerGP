# clustering.py
from sentence_transformers import SentenceTransformer
import numpy as np
from sklearn.cluster import AgglomerativeClustering
from sklearn.cluster import KMeans
from typing import List, Dict

MODEL_NAME = "all-MiniLM-L6-v2"  # small, fast, good for emails

class Clusterer:
    def __init__(self, model_name: str = MODEL_NAME):
        self.model = SentenceTransformer(model_name)

    def embed_texts(self, texts: List[str]) -> np.ndarray:
        return self.model.encode(texts, convert_to_numpy=True, show_progress_bar=False)

    def make_clusters(self, texts: List[str], distance_threshold: float = 0.25) -> Dict[int, List[int]]:
        """
        distance_threshold: lower -> more clusters; default tuned for short texts.
        returns mapping from cluster_id -> list of indices
        """
        if not texts:
            return {}
        emb = self.embed_texts(texts)
        # Agglomerative with cosine similarity converted to euclidean with normalization
        # Normalize embeddings
        from sklearn.preprocessing import normalize
        embn = normalize(emb)
        clustering = AgglomerativeClustering(n_clusters=None, distance_threshold=distance_threshold, linkage='average', metric='cosine')
        labels = clustering.fit_predict(embn)
        clusters = {}
        for i, lab in enumerate(labels):
            clusters.setdefault(int(lab), []).append(i)
        return clusters

    def make_kmeans_clusters(self, texts: List[str], k_min: int = 4, k_max: int = 20) -> Dict[int, List[int]]:
        if not texts:
            return {}

        emb = self.embed_texts(texts)

        best_k = None
        best_score = -1
        best_labels = None

        # try different cluster counts
        for k in range(k_min, k_max + 1):
            kmeans = KMeans(n_clusters=k, n_init="auto", random_state=42)
            labels = kmeans.fit_predict(emb)
            score = silhouette_score(emb, labels)

            if score > best_score:
                best_score = score
                best_k = k
                best_labels = labels

        clusters = {}
        for i, lab in enumerate(best_labels):
            clusters.setdefault(int(lab), []).append(i)

        print(f"Selected K={best_k} with silhouette={best_score:.4f}")

        return clusters