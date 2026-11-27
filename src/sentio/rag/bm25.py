import math
import re
from typing import Any, Dict, List

# Shorter words have too many one-letter neighbours ("cat", "car", "bat") to correct safely.
MIN_CORRECTABLE_LENGTH = 5
MAX_CORRECTIONS_PER_WORD = 2


def edit_distance(a: str, b: str, limit: int) -> int:
    """Optimal string alignment distance (a swap of neighbours counts once), capped at limit + 1."""
    previous2 = None
    previous = list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        current = [i] + [0] * len(b)
        for j in range(1, len(b) + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            current[j] = min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + cost)
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                current[j] = min(current[j], previous2[j - 2] + 1)
        if min(current) > limit:
            return limit + 1
        previous2, previous = previous, current
    return previous[-1]


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

    def correct_query(self, query: str) -> str:
        """The query with each misspelled word followed by the notes' word it most likely meant.

        A word is corrected only when it is absent from the indexed notes and a notes word
        within a small edit distance shares its first letter. The original word is kept,
        and a question about something the notes never mention stays unmatched.
        """
        vocabulary = self.df
        words = []
        for token in self._tokenize(query):
            words.append(token)
            if token in vocabulary or len(token) < MIN_CORRECTABLE_LENGTH or token.isdigit():
                continue
            limit = 1 if len(token) < 8 else 2
            matches = [
                term
                for term in vocabulary
                if term[0] == token[0]
                and abs(len(term) - len(token)) <= limit
                and edit_distance(token, term, limit) <= limit
            ]
            words.extend(sorted(matches)[:MAX_CORRECTIONS_PER_WORD])
        return " ".join(words)

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
