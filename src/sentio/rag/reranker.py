from typing import Any, Dict, List


class BaseReranker:
    """Abstract interface for all RAG rerankers in Sentio."""

    def rerank(
        self, query: str, hits: List[Dict[str, Any]], limit: int = 5
    ) -> List[Dict[str, Any]]:
        raise NotImplementedError


class HybridRanker(BaseReranker):
    """
    Linear fusion hybrid ranker.
    Normalizes vector cosine similarity and BM25 scores to [0, 1]
    and merges them using custom weights.
    """

    def __init__(self, w_vector: float = 0.75, w_keyword: float = 0.25):
        self.w_vector = w_vector
        self.w_keyword = w_keyword

    def rerank(
        self, query: str, hits: List[Dict[str, Any]], limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Merge and rank hits based on linear combination of normalized scores.
        Each hit should contain:
            - 'id': chunk ID
            - 'text': chunk text
            - 'payload': chunk metadata
            - 'vector_score': cosine similarity score from Qdrant [0, 1]
            - 'bm25_score': keyword search score [0, inf)
        """
        if not hits:
            return []

        # Find min/max for normalization
        vector_scores = [h.get("vector_score", 0.0) for h in hits]
        bm25_scores = [h.get("bm25_score", 0.0) for h in hits]

        min_v, max_v = min(vector_scores), max(vector_scores)
        min_k, max_k = min(bm25_scores), max(bm25_scores)

        v_range = max_v - min_v
        k_range = max_k - min_k

        epsilon = 1e-6

        reranked = []
        for hit in hits:
            v_score = hit.get("vector_score", 0.0)
            k_score = hit.get("bm25_score", 0.0)

            # Min-max normalize
            norm_v = (v_score - min_v) / (v_range + epsilon) if v_range > 0 else v_score
            norm_k = (k_score - min_k) / (k_range + epsilon) if k_range > 0 else k_score

            # Compute linear combination score
            hybrid_score = (self.w_vector * norm_v) + (self.w_keyword * norm_k)

            # Create a copy with the combined score
            new_hit = {
                "id": hit["id"],
                "text": hit["text"],
                "payload": hit["payload"],
                "vector_score": v_score,
                "bm25_score": k_score,
                "score": hybrid_score,  # standard key for final ranking
                "hybrid_score": hybrid_score,
            }
            reranked.append(new_hit)

        # Sort descending by hybrid score
        reranked.sort(key=lambda x: x["hybrid_score"], reverse=True)

        return reranked[:limit]


# Future stub for Cross-Encoder
class CrossEncoderReranker(BaseReranker):
    """
    Placeholder for future deep learning cross-encoder.
    Uses sentence-transformers cross-encoder to compute query-chunk similarity.
    """

    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        self.model_name = model_name
        self._model = None

    def _load_model(self):
        if self._model is None:
            from sentence_transformers import CrossEncoder

            self._model = CrossEncoder(self.model_name)

    def rerank(
        self, query: str, hits: List[Dict[str, Any]], limit: int = 5
    ) -> List[Dict[str, Any]]:
        if not hits:
            return []
        self._load_model()
        pairs = [(query, h["text"]) for h in hits]
        scores = self._model.predict(pairs).tolist()

        reranked = []
        for hit, score in zip(hits, scores):
            new_hit = hit.copy()
            new_hit["rerank_score"] = score
            new_hit["score"] = score
            reranked.append(new_hit)

        reranked.sort(key=lambda x: x["rerank_score"], reverse=True)
        return reranked[:limit]
