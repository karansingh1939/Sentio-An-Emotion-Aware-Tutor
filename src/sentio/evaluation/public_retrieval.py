"""Retrieval methods measured on public question-passage benchmarks.

The tutor's own pieces are imported, not re-implemented: the BM25 searcher, the hybrid
ranker and `fuse_candidates`, the merge-filter-rank step `KnowledgeBase.retrieve` runs.
The one stand-in is the vector store. The tutor asks Qdrant for the nearest passages by
cosine similarity; here the same normalised embeddings are scored with an exact dot
product, which gives the ranking an exact search returns.

Neither dataset is redistributed with Sentio. See docs/evaluation/PUBLIC_RETRIEVAL.md.
"""

import json
import math
import statistics
import time
from dataclasses import dataclass

import numpy as np

from sentio.evaluation.metrics import bootstrap_interval, ndcg, paired_bootstrap_p
from sentio.rag.bm25 import BM25Searcher
from sentio.rag.evidence_policy import MIN_DENSE_SIMILARITY
from sentio.rag.knowledge_base import fuse_candidates
from sentio.rag.reranker import HybridRanker

CANDIDATES = 20  # what KnowledgeBase.retrieve asks of each retriever
DEPTH = 10
# Prefixes each model's authors say to add.
QUERY_PREFIX = {
    "BAAI/bge-small-en-v1.5": "Represent this sentence for searching relevant passages: ",
    "intfloat/e5-small-v2": "query: ",
}
PASSAGE_PREFIX = {"intfloat/e5-small-v2": "passage: "}


@dataclass
class Dataset:
    name: str
    corpus: dict  # passage id -> text
    queries: dict  # query id -> text
    relevant: dict  # query id -> set of passage ids


def load_sciq(root):
    """School science questions, each written from one support paragraph (its gold passage)."""
    splits = {
        name: json.loads((root / "sciq" / f"{name}.json").read_text(encoding="utf-8"))
        for name in ("train", "valid", "test")
    }
    ids = {}
    for name in ("train", "valid", "test"):
        for item in splits[name]:
            support = item["support"].strip()
            if support and support not in ids:
                ids[support] = f"sciq-{len(ids)}"
    queries, relevant = {}, {}
    for number, item in enumerate(splits["test"]):
        support = item["support"].strip()
        if support:
            queries[f"q{number}"] = item["question"].strip()
            relevant[f"q{number}"] = {ids[support]}
    return Dataset("sciq", {doc: text for text, doc in ids.items()}, queries, relevant)


def load_scifact(root):
    """Scientific claims with human relevance judgements over paper abstracts (BEIR)."""
    folder = root / "scifact"
    corpus = {}
    for line in (folder / "corpus.jsonl").read_text(encoding="utf-8").splitlines():
        doc = json.loads(line)
        corpus[doc["_id"]] = f"{doc.get('title', '')} {doc['text']}".strip()
    relevant = {}
    for line in (folder / "qrels" / "test.tsv").read_text(encoding="utf-8").splitlines()[1:]:
        query, doc, score = line.split("\t")
        if int(score) > 0:
            relevant.setdefault(query, set()).add(doc)
    queries = {}
    for line in (folder / "queries.jsonl").read_text(encoding="utf-8").splitlines():
        query = json.loads(line)
        if query["_id"] in relevant:
            queries[query["_id"]] = query["text"]
    return Dataset("scifact", corpus, queries, relevant)


LOADERS = {"sciq": load_sciq, "scifact": load_scifact}


class Index:
    def __init__(self, dataset, model_name, cache_dir):
        from sentence_transformers import SentenceTransformer

        self.dataset = dataset
        self.model_name = model_name
        self.ids = list(dataset.corpus)
        self.rows = {doc: row for row, doc in enumerate(self.ids)}
        self.chunks = {
            doc: {"chunk_id": doc, "text_content": text, "document": f"{doc}.txt", "page": 1}
            for doc, text in dataset.corpus.items()
        }
        started = time.perf_counter()
        self.bm25 = BM25Searcher()
        self.bm25.index(list(self.chunks.values()))
        self.bm25_build_ms = (time.perf_counter() - started) * 1000
        self.encoder = SentenceTransformer(model_name, device="cpu", local_files_only=True)
        self.vectors = self._passage_vectors(cache_dir)

    def _passage_vectors(self, cache_dir):
        cache_dir.mkdir(parents=True, exist_ok=True)
        name = f"{self.dataset.name}-{self.model_name.replace('/', '--')}-{len(self.ids)}.npy"
        if (cache_dir / name).exists():
            return np.load(cache_dir / name)
        prefix = PASSAGE_PREFIX.get(self.model_name, "")
        vectors = self.encoder.encode(
            [prefix + self.dataset.corpus[doc] for doc in self.ids],
            batch_size=64,
            normalize_embeddings=True,
            show_progress_bar=False,
        ).astype(np.float32)
        np.save(cache_dir / name, vectors)
        return vectors

    def embed(self, query):
        prefix = QUERY_PREFIX.get(self.model_name, "")
        return self.encoder.encode(prefix + query, normalize_embeddings=True).astype(np.float32)

    def nearest(self, vector, limit):
        scores = self.vectors @ vector
        top = np.argpartition(-scores, min(limit, len(scores) - 1))[:limit]
        return [
            {"id": self.ids[row], "score": float(scores[row])}
            for row in top[np.argsort(-scores[top])]
        ]


def keyword(index, query, vector):
    return [hit["id"] for hit in index.bm25.search(query, limit=DEPTH)]


def dense(index, query, vector):
    return [hit["id"] for hit in index.nearest(vector, DEPTH)]


def _fused(index, query, vector, **switches):
    return [
        hit["id"]
        for hit in fuse_candidates(
            query,
            index.nearest(vector, CANDIDATES),
            index.bm25.search(query, limit=CANDIDATES),
            index.bm25,
            index.chunks,
            HybridRanker(),
            limit=DEPTH,
            **switches,
        )
    ]


def hybrid(index, query, vector):
    """The tutor's path: 20 + 20 candidates, similarity floor, relevance gate, weighted sum."""
    return _fused(index, query, vector)


def hybrid_unfiltered(index, query, vector):
    """The same weighted sum with the similarity floor and relevance gate switched off."""
    return _fused(index, query, vector, floor=-1.0, gate=False)


def rank_fusion(index, query, vector, depth=100, constant=60):
    """Reciprocal rank fusion (Cormack et al., 2009) of the keyword and dense rankings."""
    scores = {}
    rankings = (
        [hit["id"] for hit in index.bm25.search(query, limit=depth)],
        [hit["id"] for hit in index.nearest(vector, depth)],
    )
    for ranking in rankings:
        for rank, doc in enumerate(ranking, start=1):
            scores[doc] = scores.get(doc, 0.0) + 1.0 / (constant + rank)
    return sorted(scores, key=scores.get, reverse=True)[:DEPTH]


METHODS = {
    "keyword": keyword,
    "dense": dense,
    "hybrid": hybrid,
    "hybrid_unfiltered": hybrid_unfiltered,
    "rank_fusion": rank_fusion,
}
NEEDS_VECTOR = set(METHODS) - {"keyword"}


def measure(index, methods, limit=None):
    """Per-query scores for each method, plus what the similarity floor did to gold passages."""
    queries = list(index.dataset.queries)[:limit]
    rows = {name: {"ndcg_at_10": [], "mrr_at_10": [], "hit_at_5": [], "ms": []} for name in methods}
    gold_similarity = []
    for query_id in queries:
        query, relevant = index.dataset.queries[query_id], index.dataset.relevant[query_id]
        started = time.perf_counter()
        vector = index.embed(query)
        embed_ms = (time.perf_counter() - started) * 1000
        gold_similarity.append(
            max(float(index.vectors[index.rows[doc]] @ vector) for doc in relevant)
        )
        for name in methods:
            started = time.perf_counter()
            ranked = METHODS[name](index, query, vector)
            elapsed = (time.perf_counter() - started) * 1000
            first = next((rank for rank, doc in enumerate(ranked, 1) if doc in relevant), None)
            rows[name]["ndcg_at_10"].append(ndcg(ranked, relevant, DEPTH))
            rows[name]["mrr_at_10"].append(1 / first if first else 0.0)
            rows[name]["hit_at_5"].append(float(bool(set(ranked[:5]) & relevant)))
            rows[name]["ms"].append(elapsed + (embed_ms if name in NEEDS_VECTOR else 0.0))
    return queries, rows, gold_similarity


def summarise(rows, baseline=None):
    """Means with 95% bootstrap intervals; `baseline` is the tutor path's per-query nDCG."""
    summary = {}
    for name, row in rows.items():
        times = sorted(row["ms"])
        entry = {
            metric: {
                "mean": statistics.fmean(row[metric]),
                "interval_95": bootstrap_interval(row[metric]),
            }
            for metric in ("ndcg_at_10", "mrr_at_10", "hit_at_5")
        }
        entry["query_ms"] = {
            "median": times[len(times) // 2],
            "p95": times[max(0, math.ceil(len(times) * 0.95) - 1)],
        }
        if baseline is not None and row["ndcg_at_10"] is not baseline:
            entry["p_against_hybrid"] = paired_bootstrap_p(row["ndcg_at_10"], baseline)
        summary[name] = entry
    return summary


def floor_effect(gold_similarity):
    """How often the best gold passage scores under the tutor's similarity floor."""
    below = sum(score < MIN_DENSE_SIMILARITY for score in gold_similarity)
    ordered = sorted(gold_similarity)
    return {
        "floor": MIN_DENSE_SIMILARITY,
        "queries": len(ordered),
        "gold_below_floor": below,
        "share_below_floor": below / len(ordered),
        "gold_similarity_percentiles": {
            str(p): ordered[min(len(ordered) - 1, int(len(ordered) * p / 100))]
            for p in (5, 25, 50, 75, 95)
        },
    }
