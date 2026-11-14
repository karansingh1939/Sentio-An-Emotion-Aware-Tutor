"""Isolated evaluations against production ingestion, ownership and retrieval."""

import hashlib
import json
import platform
import tempfile
import time
from contextlib import ExitStack, contextmanager
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import psutil

from sentio.config import nlp_cfg, session_cfg
from sentio.evaluation.metrics import aggregate, retrieval_metrics
from sentio.ingestion.pipeline import DocumentIngestionPipeline
from sentio.rag.evidence_policy import MIN_DENSE_SIMILARITY
from sentio.rag.knowledge_base import KnowledgeBase, SemanticRetriever
from sentio.rag.reranker import HybridRanker
from sentio.rag.vector_db import QdrantVectorDB
from sentio.repositories.documents import DocumentRepository
from sentio.session.manager import SessionManager


class KeywordOnly:
    def encode(self, *args, **kwargs):
        raise RuntimeError("Evaluation explicitly uses keyword retrieval")


@contextmanager
def isolated_runtime(model):
    """Never scan, modify or read the learner's real database or uploads."""
    with tempfile.TemporaryDirectory(prefix="sentio-eval-") as directory, ExitStack() as stack:
        root = Path(directory)
        stack.enter_context(patch.object(session_cfg, "DB_URL", f"sqlite:///{root / 'eval.db'}"))
        stack.enter_context(patch.object(session_cfg, "SESSION_LOG_PATH", root / "sessions"))
        stack.enter_context(patch("sentio.ingestion.pipeline.DATA_DIR", root))
        sm = SessionManager()
        sm.load()
        owner = sm.persister.auth_service.register_student("eval@example.test", "Evaluation-2026!")
        sm.persister.auth_service.login_student("eval@example.test", "Evaluation-2026!")
        vdb = QdrantVectorDB(mode="memory")
        vdb.connect()
        vdb.create_collection_if_not_exists(vector_size=384)
        pipeline = DocumentIngestionPipeline(sm, vdb)
        pipeline._embedding_model = model
        retriever = SemanticRetriever()
        retriever._model = model
        kb = KnowledgeBase(doc_repo=DocumentRepository(sm.persister), vdb=vdb, retriever=retriever)
        try:
            yield sm, pipeline, kb, owner.student_id
        finally:
            vdb.client.close()
            sm.persister._engine.dispose()


def _ingest(sm, pipeline, dataset_dir, dataset, owner, model):
    documents = {}
    for filename in dataset["documents"]:
        if not pipeline.process_file(dataset_dir / filename, "reference", "general", owner):
            raise RuntimeError(f"Evaluation ingestion failed: {filename}")
        saved = sm.get_document_by_filename(filename, owner, "reference")
        documents[filename] = saved["id"]
        if not isinstance(model, KeywordOnly) and not saved["embedding_count"]:
            raise RuntimeError(f"Hybrid evaluation requires indexed vectors: {filename}")
    return documents


def _relevant_chunks(sm, documents, case):
    if not case["expected_document"]:
        return []
    chunks = sm.get_document_chunks(documents[case["expected_document"]])
    relevant = [
        c["chunk_id"] for c in chunks if case["support"].lower() in c["text_content"].lower()
    ]
    if not relevant:
        raise ValueError(f"Rubric support absent from indexed source: {case['id']}")
    return relevant


def _summarise(rows):
    summary = aggregate(rows)
    positives = [r for r in rows if r["document_hit"] is not None]
    summary["document_hit_rate"] = sum(r["document_hit"] for r in positives) / len(positives)
    return summary


def measure_retrieval(dataset_dir, dataset, model):
    with isolated_runtime(model) as (sm, pipeline, kb, owner):
        documents = _ingest(sm, pipeline, dataset_dir, dataset, owner, model)
        rows = []
        for case in dataset["queries"]:
            relevant = _relevant_chunks(sm, documents, case)
            started = time.perf_counter()
            content = kb.retrieve(
                "general",
                "evaluation",
                "beginner",
                "neutral",
                query=case["query"],
                student_id=owner,
                document_id=list(documents.values()),
            )
            latency = (time.perf_counter() - started) * 1000
            row = dict(case, **retrieval_metrics(content.chunks_used, relevant), latency_ms=latency)
            row["document_hit"] = (
                float(
                    any(
                        c["filename"] == case["expected_document"] for c in content.source_citations
                    )
                )
                if relevant
                else None
            )
            row["ranked_chunks"] = content.chunks_used
            rows.append(row)
        return {"summary": _summarise(rows), "cases": rows}


def measure_dense(dataset_dir, dataset, model):
    """Embedding similarity alone, with no score floor and no keyword filter.

    The product never retrieves this way. It is the reference that shows what the hybrid
    path's similarity floor removes.
    """
    with isolated_runtime(model) as (sm, pipeline, _kb, owner):
        documents = _ingest(sm, pipeline, dataset_dir, dataset, owner, model)
        names = {doc_id: filename for filename, doc_id in documents.items()}
        chunks = [
            dict(chunk, filename=names[doc_id])
            for doc_id in documents.values()
            for chunk in sm.get_document_chunks(doc_id)
        ]
        vectors = model.encode([c["text_content"] for c in chunks], normalize_embeddings=True)
        rows = []
        for case in dataset["queries"]:
            relevant = _relevant_chunks(sm, documents, case)
            started = time.perf_counter()
            scores = (vectors @ model.encode(case["query"], normalize_embeddings=True)).tolist()
            order = sorted(range(len(chunks)), key=lambda i: -scores[i])[:5]
            latency = (time.perf_counter() - started) * 1000
            ranked = [chunks[i]["chunk_id"] for i in order]
            row = dict(case, **retrieval_metrics(ranked, relevant), latency_ms=latency)
            row["document_hit"] = (
                float(any(chunks[i]["filename"] == case["expected_document"] for i in order))
                if relevant
                else None
            )
            row["ranked_chunks"] = ranked
            row["top_similarity"] = scores[order[0]]
            row["relevant_similarity"] = (
                max(s for s, c in zip(scores, chunks) if c["chunk_id"] in relevant)
                if relevant
                else None
            )
            rows.append(row)
        summary = _summarise(rows)
        # Unlike the product paths, this reference always returns its five nearest passages.
        summary["irrelevant_candidate_rate"] = None
        wanted = [r["relevant_similarity"] for r in rows if r["relevant_similarity"] is not None]
        unwanted = [r["top_similarity"] for r in rows if r["relevant_similarity"] is None]
        summary["similarity_floor"] = MIN_DENSE_SIMILARITY
        summary["relevant_below_floor"] = sum(s < MIN_DENSE_SIMILARITY for s in wanted)
        summary["lowest_relevant_similarity"] = min(wanted)
        summary["highest_unanswerable_similarity"] = max(unwanted) if unwanted else None
        return {"summary": summary, "cases": rows}


def measure_grading(dataset):
    from sentio.ai.providers import OllamaBackend
    from sentio.quiz.service import QuizService, numeric_value

    backend = OllamaBackend()
    backend.load()
    service = QuizService(SimpleNamespace(nlp=SimpleNamespace(_backend=backend)))
    rows = []
    for case in dataset["grading"]:
        exact = case["answer"].strip().lower() == case["reference"].strip().lower()
        start = time.perf_counter()
        try:
            correct, score = service._grade_short_answer(
                case["question"], case["reference"], case["answer"]
            )
            passed = (
                correct == case["expected_correct"]
                and case["score_range"][0] <= score <= case["score_range"][1]
            )
            result = {"correct": correct, "score": score, "rubric_pass": passed}
        except Exception as exc:
            result = {"error": str(exc), "rubric_pass": False}
        rows.append(
            dict(
                case,
                category="blank"
                if not case["answer"].strip()
                else "exact"
                if exact
                else "numeric"
                if numeric_value(case["answer"]) is not None
                and numeric_value(case["reference"]) is not None
                else "semantic",
                latency_ms=(time.perf_counter() - start) * 1000,
                **result,
            )
        )
    tags = backend._session.get(f"{nlp_cfg.OLLAMA_BASE_URL}/api/tags", timeout=5).json()
    model = next((m for m in tags.get("models", []) if m["name"] == nlp_cfg.OLLAMA_MODEL), {})
    return {
        "model": backend.name,
        "model_digest": model.get("digest"),
        "temperature": 0.0,
        "cases": rows,
    }


def evaluate(dataset_dir, grade=False):
    from sentence_transformers import SentenceTransformer

    dataset_dir = Path(dataset_dir)
    raw = (dataset_dir / "dataset.json").read_bytes()
    dataset = json.loads(raw)
    digest = hashlib.sha256(raw)
    for filename in dataset["documents"]:
        digest.update((dataset_dir / filename).read_bytes())
    model = SentenceTransformer(nlp_cfg.EMBEDDING_MODEL, device="cpu", local_files_only=True)
    result = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dataset_version": dataset["version"],
        "dataset_sha256": digest.hexdigest(),
        "provenance": dataset["provenance"],
        "packages": {
            name: version(name)
            for name in ("sentence-transformers", "torch", "qdrant-client", "pypdf")
        },
        "hardware": {
            "platform": platform.platform(),
            "cpu": platform.processor(),
            "logical_cpus": psutil.cpu_count(),
            "ram_bytes": psutil.virtual_memory().total,
        },
        "configuration": {
            "embedding_model": nlp_cfg.EMBEDDING_MODEL,
            "device": "cpu",
            "top_k": 5,
            "vector_weight": HybridRanker().w_vector,
            "keyword_weight": HybridRanker().w_keyword,
            "similarity_floor": MIN_DENSE_SIMILARITY,
            "chunk_size": 500,
            "chunk_overlap": 100,
            "longest_document_characters": max(
                len((dataset_dir / filename).read_text(encoding="utf-8"))
                for filename in dataset["documents"]
            ),
            "fresh_owned_database": True,
        },
        "retrieval": {},
    }
    for mode, encoder in (("keyword", KeywordOnly()), ("hybrid", model)):
        result["retrieval"][mode] = measure_retrieval(dataset_dir, dataset, encoder)
    result["retrieval"]["dense_reference"] = measure_dense(dataset_dir, dataset, model)
    if grade:
        result["grading"] = measure_grading(dataset)
    return result
