import math
import re
from typing import Any, Dict, List


class BM25Searcher:
    """
    Lightweight, pure-Python BM25 keyword search implementation.
    Designed for search over document chunks in Sentio.
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.corpus_size = 0
        self.avg_doc_len = 0.0
        self.doc_lengths = {}  # doc_id -> length in tokens
        self.doc_term_freqs = {}  # doc_id -> {term -> freq}
        self.doc_texts = {}  # doc_id -> raw text
        self.doc_metadatas = {}  # doc_id -> metadata dict
        self.df = {}  # term -> doc frequency
        self.idf = {}  # term -> IDF score

    def _tokenize(self, text: str) -> List[str]:
        """Simple tokenizer that lowercases, removes punctuation, and splits by whitespace."""
        cleaned = re.sub(r"[^\w\s\-]", " ", text.lower())
        return [word for word in cleaned.split() if len(word) > 1]

    def index(self, chunks: List[Dict[str, Any]]):
        """
        Build the BM25 index from a list of document chunks.
        Each chunk is expected to be a dictionary containing:
            - 'chunk_id' or 'id'
            - 'text_content' or 'text'
            - metadata fields
        """
        self.corpus_size = len(chunks)
        if self.corpus_size == 0:
            self.avg_doc_len = 0.0
            return

        total_len = 0
        self.doc_lengths = {}
        self.doc_term_freqs = {}
        self.doc_texts = {}
        self.doc_metadatas = {}
        self.df = {}
        self.idf = {}

        for chunk in chunks:
            chunk_id = chunk.get("chunk_id") or chunk.get("id")
            text = chunk.get("text_content") or chunk.get("text") or ""

            # Extract metadata
            metadata = {
                k: v
                for k, v in chunk.items()
                if k not in ["chunk_id", "id", "text_content", "text"]
            }
            self.doc_texts[chunk_id] = text
            self.doc_metadatas[chunk_id] = metadata

            tokens = self._tokenize(text)
            doc_len = len(tokens)
            self.doc_lengths[chunk_id] = doc_len
            total_len += doc_len

            # Calculate term frequencies inside doc
            freqs = {}
            unique_terms = set(tokens)
            for token in tokens:
                freqs[token] = freqs.get(token, 0) + 1
            self.doc_term_freqs[chunk_id] = freqs

            # Update document frequency for IDF
            for term in unique_terms:
                self.df[term] = self.df.get(term, 0) + 1

        self.avg_doc_len = total_len / self.corpus_size

        # Precompute IDF for all terms in the corpus
        for term, freq in self.df.items():
            # BM25 standard IDF with smoothing
            self.idf[term] = math.log((self.corpus_size - freq + 0.5) / (freq + 0.5) + 1.0)

    def search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Search the BM25 index for a query.
        Returns a sorted list of hits, where each hit is a dictionary:
            - 'id': chunk ID
            - 'score': raw BM25 score
            - 'text': raw chunk text
            - 'payload': metadata dictionary
        """
        query_tokens = self._tokenize(query)
        if not query_tokens or self.corpus_size == 0:
            return []

        scores = {}
        for doc_id, freqs in self.doc_term_freqs.items():
            doc_len = self.doc_lengths[doc_id]
            score = 0.0

            for token in query_tokens:
                if token not in freqs:
                    continue

                tf = freqs[token]
                idf_val = self.idf.get(token, 0.0)

                # BM25 formula
                numerator = tf * (self.k1 + 1)
                denominator = tf + self.k1 * (1.0 - self.b + self.b * (doc_len / self.avg_doc_len))
                score += idf_val * (numerator / denominator)

            if score > 0.0:
                scores[doc_id] = score

        # Sort scores and construct result payload
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:limit]

        results = []
        for doc_id, score in sorted_scores:
            results.append(
                {
                    "id": doc_id,
                    "score": score,
                    "text": self.doc_texts[doc_id],
                    "payload": self.doc_metadatas[doc_id],
                }
            )

        return results


if __name__ == "__main__":
    # Smoke test for BM25 Searcher
    chunks = [
        {
            "id": "c1",
            "text": "Calculus limits are fundamental to derivatives.",
            "subject": "mathematics",
        },
        {
            "id": "c2",
            "text": "Linear algebra uses vectors and matrices to solve linear equations.",
            "subject": "mathematics",
        },
        {
            "id": "c3",
            "text": "Python is a high-level programming language used in AI.",
            "subject": "computer_science",
        },
    ]

    searcher = BM25Searcher()
    searcher.index(chunks)

    print("Testing BM25 search for 'limits'...")
    hits = searcher.search("limits", limit=2)
    print(f"Hits: {hits}")
    assert len(hits) == 1 and hits[0]["id"] == "c1", "Failed to retrieve c1"

    print("Testing BM25 search for 'linear language'...")
    hits = searcher.search("linear language", limit=2)
    print(f"Hits: {hits}")
    assert len(hits) == 2 and hits[0]["id"] == "c2", "Failed to rank c2 highest"

    print("BM25 smoke test passed successfully!")
