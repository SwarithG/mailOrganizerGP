# clustering.py
from sentence_transformers import SentenceTransformer
import numpy as np
from sklearn.cluster import AgglomerativeClustering, KMeans
from sklearn.preprocessing import normalize
from typing import List, Dict, Optional

MODEL_NAME = "all-MiniLM-L6-v2"  # Small + fast model good for email clustering

class Clusterer:
    def __init__(self, model_name: str = MODEL_NAME):
        self.model = SentenceTransformer(model_name)

    # -----------------------------
    # EMBEDDING
    # -----------------------------
    def embed_texts(self, texts: List[str]) -> np.ndarray:
        """Embeds a list of text strings."""
        return self.model.encode(texts, convert_to_numpy=True, show_progress_bar=False)

    # -----------------------------
    # AGGLOMERATIVE CLUSTERING
    # -----------------------------
    def agglomerative(
        self,
        texts: List[str],
        distance_threshold: float = 0.35
    ) -> Dict[int, List[int]]:
        """
        Hierarchical clustering using cosine distance.
        Lower threshold -> more clusters
        """
        if not texts:
            return {}

        emb = self.embed_texts(texts)
        emb = normalize(emb)  # required for cosine metric

        clustering = AgglomerativeClustering(
            n_clusters=None,
            distance_threshold=distance_threshold,
            linkage="average",
            metric="cosine"
        )

        labels = clustering.fit_predict(emb)

        clusters: Dict[int, List[int]] = {}
        for idx, lab in enumerate(labels):
            clusters.setdefault(int(lab), []).append(idx)

        return clusters

    # -----------------------------
    # KMEANS CLUSTERING
    # -----------------------------
    def kmeans(self, texts: List[str], k: int = 7) -> Dict[int, List[int]]:
        """
        KMeans clustering. User must provide k.
        """
        if not texts:
            return {}

        emb = self.embed_texts(texts)
        emb = normalize(emb)

        km = KMeans(n_clusters=k, random_state=42, n_init='auto')
        labels = km.fit_predict(emb)

        clusters: Dict[int, List[int]] = {}
        for idx, lab in enumerate(labels):
            clusters.setdefault(int(lab), []).append(idx)

        return clusters

    # -----------------------------
    # UNIFIED CLUSTER FUNCTION
    # -----------------------------
    def cluster(
        self,
        texts: List[str],
        method: str = "agglomerative",
        distance_threshold: float = 0.35,
        k: Optional[int] = None
    ) -> Dict[int, List[int]]:
        """
        Unified interface:
        - method="agglomerative": use hierarchical clustering
        - method="kmeans": use kmeans clustering
        """
        method = method.lower()

        if method == "agglomerative":
            return self.agglomerative(texts, distance_threshold)

        elif method == "kmeans":
            if k is None:
                raise ValueError("k must be provided when method='kmeans'.")
            return self.kmeans(texts, k)

        else:
            raise ValueError("method must be either 'agglomerative' or 'kmeans'.")

    def pick_threshold(self, texts: List[str], emb: np.ndarray):
        n = len(texts)
        if n < 200:
            return 0.6
        elif n < 500:
            return 0.40
        elif n < 1000:
            return 0.36
        else:
            return 0.33   # large inbox → slightly tighter

    # -------------------------
    # SIMPLE K SELECTION
    # -------------------------
    def pick_k(self, cluster_size: int) -> int:
        if cluster_size <= 8:
            return 1  # don’t subdivide tiny clusters
        # heuristic: k grows slowly with size
        return min(6, max(2, int(np.log(cluster_size) + 1)))

    # -------------------------
    # MAIN HYBRID CLUSTERING
    # -------------------------
    def hybrid_clusters(self, texts: List[str]) -> Dict[int, List[int]]:
        if not texts:
            return {}

        # 1. Embed
        emb = self.embed_texts(texts)
        emb_norm = normalize(emb)

        # 2. Adaptive threshold selection
        threshold = self.pick_threshold(texts, emb)

        # 3. First pass: Agglomerative
        agg = AgglomerativeClustering(
            n_clusters=None,
            distance_threshold=threshold,
            linkage='average',
            metric='cosine'
        )
        agg_labels = agg.fit_predict(emb_norm)

        first_pass = {}
        for idx, lbl in enumerate(agg_labels):
            first_pass.setdefault(int(lbl), []).append(idx)

        # 4. Second pass: refine each large cluster using KMeans
        final_clusters = {}
        next_id = 0

        for _, indices in first_pass.items():
            cluster_size = len(indices)

            if cluster_size <= 8:
                # keep tiny clusters as-is
                final_clusters[next_id] = indices
                next_id += 1
                continue

            # get K
            k = self.pick_k(cluster_size)

            # run kmeans inside this cluster
            sub_emb = emb_norm[indices]
            km = KMeans(n_clusters=k, random_state=42, n_init="auto")
            sub_labels = km.fit_predict(sub_emb)

            # store subdivided clusters
            for sub_lab in range(k):
                subcluster_indices = [indices[i] for i in range(cluster_size) if sub_labels[i] == sub_lab]
                final_clusters[next_id] = subcluster_indices
                next_id += 1

        return final_clusters
    
    def cluster_signature(self,cluster_mids):
        return tuple(sorted(cluster_mids))