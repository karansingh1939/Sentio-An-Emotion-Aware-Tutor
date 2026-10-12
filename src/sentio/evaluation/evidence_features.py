"""Offline CPU feature extraction, reusing Sentio's keyword and reranking code."""

import hashlib
import platform
import time
from importlib.metadata import version
from types import SimpleNamespace

from sentio.evaluation.evidence_dataset import digest, pair_hash, tokens
from sentio.rag.bm25 import BM25Searcher
from sentio.rag.reranker import CrossEncoderReranker, HybridRanker

FEATURES = [
    "embedding_similarity",
    "keyword_score",
    "query_overlap",
    "query_length",
    "passage_length",
    "retrieval_rank",
    "best_score_gap",
]


def collect_features(corpus, encoder=None, cross_encoder=None):
    import numpy as np
    import psutil

    process = psutil.Process()
    started = time.perf_counter()
    pairs, queries = [], []
    for split in ("train", "validation", "test"):
        documents = [d for d in corpus["documents"] if d["split"] == split]
        questions = [q for q in corpus["questions"] if q["split"] == split]
        chunks = [{"id": d["document_id"], "text": d["text"]} for d in documents]
        searcher = BM25Searcher()
        searcher.index(chunks)
        vectors = (
            encoder.encode(
                [d["text"] for d in documents], normalize_embeddings=True, show_progress_bar=False
            )
            if encoder
            else None
        )
        for question in questions:
            tick = time.perf_counter()
            keyword = {
                h["id"]: h["score"] for h in searcher.search(question["text"], limit=len(documents))
            }
            keyword_ms = (time.perf_counter() - tick) * 1000
            tick = time.perf_counter()
            similarities = (
                (
                    np.asarray(vectors)
                    @ encoder.encode(
                        [question["text"]], normalize_embeddings=True, show_progress_bar=False
                    )[0]
                ).tolist()
                if encoder
                else [None] * len(documents)
            )
            dense_ms = (time.perf_counter() - tick) * 1000 if encoder else None
            hits = [
                {
                    "id": d["document_id"],
                    "text": d["text"],
                    "payload": {},
                    "bm25_score": keyword.get(d["document_id"], 0),
                    "vector_score": similarities[i] if encoder else 0,
                }
                for i, d in enumerate(documents)
            ]
            tick = time.perf_counter()
            fused = HybridRanker().rerank(question["text"], hits, limit=len(hits))
            fusion_ms = (time.perf_counter() - tick) * 1000
            hybrid = {h["id"]: (rank, h["score"]) for rank, h in enumerate(fused, 1)}
            gap = fused[0]["score"] - fused[1]["score"] if len(fused) > 1 else 0
            cross = {}
            cross_ms = None
            if encoder and cross_encoder:
                tick = time.perf_counter()
                ranked = cross_encoder.rerank(question["text"], fused[:10], limit=10)
                cross_ms = (time.perf_counter() - tick) * 1000
                cross = {h["id"]: h["score"] for h in ranked}
            q_tokens = tokens(question["text"])
            for index, document in enumerate(documents):
                document_id = document["document_id"]
                rank, score = hybrid[document_id]
                values = [
                    similarities[index],
                    keyword.get(document_id, 0),
                    len(q_tokens & tokens(document["text"])) / max(1, len(q_tokens)),
                    len(question["text"].split()),
                    len(document["text"].split()),
                    rank,
                    gap,
                ]
                pairs.append(
                    {
                        "pair_id": f"{question['question_id']}::{document_id}",
                        "question_id": question["question_id"],
                        "document_id": document_id,
                        "topic": question["topic"],
                        "split": split,
                        "pair_hash": pair_hash(question, document),
                        "features": values,
                        "scores": {
                            "keyword": keyword.get(document_id, 0),
                            "dense": similarities[index],
                            "hybrid": score if encoder else None,
                            "cross_encoder": cross.get(document_id),
                        },
                        "proposed_label": int(document_id in question["proposed_support"]),
                        "review_status": "pending_human_review",
                    }
                )
            queries.append(
                {
                    "question_id": question["question_id"],
                    "split": split,
                    "topic": question["topic"],
                    "latency_ms": {
                        "keyword": keyword_ms,
                        "dense": dense_ms,
                        "hybrid": keyword_ms + dense_ms + fusion_ms if encoder else None,
                        "cross_encoder": keyword_ms + dense_ms + fusion_ms + cross_ms
                        if cross_ms is not None
                        else None,
                    },
                }
            )
    return {
        "version": 1,
        "corpus_hash": digest(corpus),
        "feature_names": FEATURES,
        "mode": "cached_cpu" if encoder else "keyword_only_annotation_preview",
        "encoder": getattr(encoder, "model_name", None),
        "encoder_digest": getattr(encoder, "weights_hash", None),
        "cross_encoder": getattr(cross_encoder, "model_name", None),
        "cross_encoder_digest": getattr(cross_encoder, "weights_hash", None),
        "failures": getattr(encoder, "failures", []) if encoder else [],
        "hardware": {
            "platform": platform.platform(),
            "processor": platform.processor(),
            "rss_bytes": process.memory_info().rss,
        },
        "versions": {
            name: version(name) for name in ("numpy", "scikit-learn", "sentence-transformers")
        },
        "elapsed_seconds": time.perf_counter() - started,
        "queries": queries,
        "pairs": pairs,
    }


def cached_models(model_name):
    from sentence_transformers import SentenceTransformer

    encoder = SentenceTransformer(model_name, device="cpu", local_files_only=True)
    wrapper = SimpleNamespace(
        model_name=model_name, encode=encoder.encode, weights_hash=weight_digest(encoder)
    )
    reranker = CrossEncoderReranker()
    try:
        reranker._load_model()  # No model download.
        reranker.weights_hash = weight_digest(reranker._model.model)
    except OSError:
        wrapper.failures = ["Existing cross-encoder weights are unavailable in the local cache."]
        reranker = None
    return wrapper, reranker


def weight_digest(model):
    import torch

    hasher = hashlib.sha256()
    for name, parameter in sorted(model.state_dict().items()):
        hasher.update(name.encode())
        hasher.update(str(tuple(parameter.shape)).encode())
        hasher.update(str(parameter.dtype).encode())
        hasher.update(
            parameter.detach().cpu().contiguous().reshape(-1).view(torch.uint8).numpy().tobytes()
        )
    return hasher.hexdigest()
