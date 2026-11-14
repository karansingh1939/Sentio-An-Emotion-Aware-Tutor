"""
knowledge_base.py: retrieval over the learner's own notes.

KnowledgeBase.retrieve runs hybrid search (BM25 + MiniLM embeddings in Qdrant) over the
selected notes and returns a RetrievedContent package with the passages, citations and
an evidence outcome. When nothing relevant is found, or no notes are selected, the
outcome tells the tutor workflow to refuse instead of calling the model.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from sentio.config import nlp_cfg, tutor_cfg
from sentio.rag.evidence_policy import MIN_DENSE_SIMILARITY, has_relevance_signal

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# ENUMS & CONSTANTS
# ─────────────────────────────────────────────


class Difficulty(str, Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"

    def step_up(self) -> "Difficulty":
        order = [Difficulty.BEGINNER, Difficulty.INTERMEDIATE, Difficulty.ADVANCED]
        idx = order.index(self)
        return order[min(idx + 1, len(order) - 1)]

    def step_down(self) -> "Difficulty":
        order = [Difficulty.BEGINNER, Difficulty.INTERMEDIATE, Difficulty.ADVANCED]
        idx = order.index(self)
        return order[max(idx - 1, 0)]


@dataclass
class RetrievedContent:
    """
    Assembled content package for a single tutoring response.
    The tutor agent reads this to construct its message.
    """

    subject: str
    topic: str
    difficulty: Difficulty
    learning_state: str
    strategy: str

    # Metadata
    chunks_used: List[str] = field(default_factory=list)  # chunk_ids

    # RAG dynamic fields
    source_citations: List[dict] = field(default_factory=list)
    rag_diagnostics: Dict[str, Any] = field(default_factory=dict)
    is_rag: bool = False
    evidence_outcome: str = "general"
    rag_context: Optional[str] = None

    def has_content(self) -> bool:
        return bool(self.is_rag and self.rag_context)


# ─────────────────────────────────────────────
# SEMANTIC RETRIEVER
# ─────────────────────────────────────────────


class SemanticRetriever:
    """Lazily loads the sentence-transformers model used to embed queries."""

    def __init__(self, model_name: str = nlp_cfg.EMBEDDING_MODEL):
        self.model_name = model_name
        self._model = None

    def _load_model(self):
        """Lazy-load sentence-transformers model."""
        if self._model is not None:
            return
        try:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name, device="cpu", local_files_only=True)
            logger.info(f"Semantic retriever loaded: {self.model_name}")
        except ImportError:
            logger.warning(
                "sentence-transformers not installed. "
                "Falling back to keyword search. "
                "Run: pip install sentence-transformers"
            )
        except Exception as e:
            logger.warning(
                f"Failed to load sentence-transformers model '{self.model_name}': {e}. "
                "Falling back to keyword search."
            )
            self._model = None


# ─────────────────────────────────────────────
# CONTENT ADAPTER
# ─────────────────────────────────────────────


class ContentAdapter:
    """Maps a teaching strategy to a tone instruction."""

    # Strategy → tone instruction (injected into prompts)
    STRATEGY_TONE: Dict[str, str] = {
        "challenge": "Be concise and push the student further. Pose a harder extension.",
        "standard": "Explain clearly and methodically. Check understanding at the end.",
        "explore": "Be enthusiastic. Show unexpected connections. Go deeper than asked.",
        "simplify": "Use very simple language. Break into tiny steps. Use everyday analogies.",
        "reassure": "Be warm and encouraging. Celebrate small progress. Avoid jargon.",
        "reframe": "Try a completely different angle. Use a fresh analogy or visual metaphor.",
        "motivate": "Make it exciting. Connect to real-world applications. Use a story hook.",
    }

    def get_tone(self, strategy: str) -> str:
        return self.STRATEGY_TONE.get(strategy, "Explain clearly and helpfully.")


# ─────────────────────────────────────────────
# KNOWLEDGE BASE (Facade)
# ─────────────────────────────────────────────


def bm25_score_for(searcher, query: str, doc_id: str) -> float:
    """BM25 score of one indexed chunk for a query."""
    query_tokens = searcher._tokenize(query)
    if not query_tokens or doc_id not in searcher.doc_term_freqs:
        return 0.0

    freqs = searcher.doc_term_freqs[doc_id]
    doc_len = searcher.doc_lengths[doc_id]
    score = 0.0

    for token in query_tokens:
        if token not in freqs:
            continue
        tf = freqs[token]
        idf_val = searcher.idf.get(token, 0.0)
        numerator = tf * (searcher.k1 + 1)
        denominator = tf + searcher.k1 * (
            1.0 - searcher.b + searcher.b * (doc_len / searcher.avg_doc_len)
        )
        score += idf_val * (numerator / denominator)

    return score


def fuse_candidates(
    query,
    vector_results,
    bm25_results,
    bm25_searcher,
    chunks_by_id,
    ranker,
    limit=5,
    floor=MIN_DENSE_SIMILARITY,
    gate=True,
):
    """Merge vector and keyword hits, drop those with no relevance signal, and rank them.

    `floor` and `gate` exist so evaluations can switch each filter off; the tutor always
    uses the defaults.
    """
    merged_hits = {}
    for hit in vector_results:
        if hit["score"] < floor:
            continue
        cid = hit["id"]
        if cid not in chunks_by_id:
            continue
        merged_hits[cid] = {
            "id": cid,
            "text": chunks_by_id[cid]["text_content"],
            "payload": chunks_by_id[cid],
            "vector_score": hit["score"],
            "bm25_score": 0.0,
        }

    for hit in bm25_results:
        cid = hit["id"]
        if cid not in merged_hits:
            merged_hits[cid] = {
                "id": cid,
                "text": hit["text"],
                "payload": hit["payload"],
                "vector_score": 0.0,
                "bm25_score": hit["score"],
            }
        else:
            merged_hits[cid]["bm25_score"] = hit["score"]

    for cid, hit in merged_hits.items():
        if hit["bm25_score"] == 0.0:
            hit["bm25_score"] = bm25_score_for(bm25_searcher, query, cid)

    candidates = [
        hit
        for hit in merged_hits.values()
        if not gate or has_relevance_signal(query, hit["text"], hit.get("vector_score", 0))
    ]
    return ranker.rerank(query, candidates, limit=limit)


class KnowledgeBase:
    """
    Main interface used by the TutorAgent.

    Example:
        kb = KnowledgeBase()
        kb.load()

        content = kb.retrieve(
            subject="mathematics",
            topic="derivatives",
            difficulty="intermediate",
            learning_state="struggling",
            query="I don't understand the chain rule"
        )
    """

    def __init__(
        self,
        retriever: Optional[SemanticRetriever] = None,
        adapter: Optional[ContentAdapter] = None,
        vdb: Optional[Any] = None,
        doc_repo: Optional[Any] = None,
        ranker: Optional[Any] = None,
    ):
        self.retriever = retriever or SemanticRetriever()
        self.adapter = adapter or ContentAdapter()

        # Connect to SQLite Document registry and Qdrant client
        from sentio.rag.reranker import HybridRanker
        from sentio.rag.vector_db import QdrantVectorDB
        from sentio.repositories.documents import DocumentRepository

        self.vdb = vdb or QdrantVectorDB()
        self.doc_repo = doc_repo or DocumentRepository()
        self.ranker = ranker or HybridRanker(w_vector=0.75, w_keyword=0.25)

    def load(self):
        """Open the document registry and the vector index."""
        self.doc_repo.load()
        self.vdb.connect()
        logger.info("KnowledgeBase ready.")

    def retrieve(
        self,
        subject: str,
        topic: str,
        difficulty: str,
        learning_state: str,
        query: Optional[str] = None,
        session_id: Optional[str] = None,
        student_id: Optional[str] = None,
        document_id: Optional[Any] = None,
    ) -> RetrievedContent:
        """
        Main retrieval method. Returns a RetrievedContent package.
        Supports hybrid RAG retrieval if documents are indexed,
        with fallback to built-in static curriculum store.
        """
        import time

        diff = Difficulty(difficulty)
        strategy = tutor_cfg.STRATEGY_MAP.get(learning_state, "standard")

        content = RetrievedContent(
            subject=subject,
            topic=topic,
            difficulty=diff,
            learning_state=learning_state,
            strategy=strategy,
        )

        if student_id:
            from sentio.repositories.courses import expand_source

            with self.doc_repo.persister._engine.connect() as connection:
                document_id = expand_source(connection, student_id, document_id)

        # Check if we have documents indexed and allowed for this student
        has_docs = False
        registered_docs = []
        if student_id and document_id and document_id != "none":
            registered_docs = self.doc_repo.list_documents(student_id=student_id)
            if document_id == "all":
                has_docs = any(d["status"] == "indexed" for d in registered_docs)
            elif isinstance(document_id, list):
                # Verify student ownership of all requested document IDs
                allowed_ids = {d["id"] for d in registered_docs if d["status"] == "indexed"}
                if all(did in allowed_ids for did in document_id):
                    has_docs = True
            else:
                # Specific document ID string
                has_docs = any(
                    d["id"] == document_id and d["status"] == "indexed" for d in registered_docs
                )

        if query and has_docs:
            t_rag_start = time.perf_counter()

            # 1. Fetch query vector using retriever's lazy-loaded sentence-transformer model
            query_vector = []
            t_emb_start = time.perf_counter()
            vector_docs = [
                d
                for d in registered_docs
                if d.get("embedding_count", 0) > 0
                and (
                    document_id == "all"
                    or d["id"] == document_id
                    or isinstance(document_id, list)
                    and d["id"] in document_id
                )
            ]
            if vector_docs and self.vdb.is_available():
                try:
                    self.retriever._load_model()
                    if self.retriever._model:
                        query_vector = self.retriever._model.encode(
                            [query], normalize_embeddings=True
                        )[0].tolist()
                except Exception as exc:
                    logger.warning("Query embedding unavailable; using keyword search: %s", exc)
            t_emb_end = time.perf_counter()
            emb_latency = (t_emb_end - t_emb_start) * 1000

            # 2. Perform vector search in Qdrant
            t_v_start = time.perf_counter()
            vector_results = []
            if query_vector:
                if self.vdb.is_available():
                    # Build search filter securely
                    filter_payload = {}
                    if student_id:
                        filter_payload["student_id"] = student_id
                    if document_id != "all":
                        filter_payload["document_id"] = document_id

                    vector_results = self.vdb.search(
                        query_vector=query_vector, limit=20, filter_payload=filter_payload
                    )
                else:
                    logger.warning(
                        "Qdrant vector database is unavailable. Skipping vector search, using BM25 keyword search only."
                    )
            t_v_end = time.perf_counter()
            vector_latency = (t_v_end - t_v_start) * 1000

            # 3. Perform BM25 search in SQLite
            t_k_start = time.perf_counter()
            all_db_chunks = self.doc_repo.get_all_chunks(student_id=student_id)
            if document_id == "all":
                subj_chunks = all_db_chunks
            elif isinstance(document_id, list):
                subj_chunks = [c for c in all_db_chunks if c.get("document_id") in document_id]
            else:
                subj_chunks = [c for c in all_db_chunks if c.get("document_id") == document_id]

            from sentio.rag.bm25 import BM25Searcher

            bm25_searcher = BM25Searcher()
            bm25_searcher.index(subj_chunks)
            bm25_results = bm25_searcher.search(query, limit=20)
            t_k_end = time.perf_counter()
            keyword_latency = (t_k_end - t_k_start) * 1000

            # 4. Merge candidates, back-fill scores, filter and rank
            db_chunk_map = {c["chunk_id"]: c for c in subj_chunks}
            t_rank_start = time.perf_counter()
            top_ranked = fuse_candidates(
                query, vector_results, bm25_results, bm25_searcher, db_chunk_map, self.ranker
            )
            t_rank_end = time.perf_counter()
            ranking_latency = (t_rank_end - t_rank_start) * 1000

            total_rag_latency = (time.perf_counter() - t_rag_start) * 1000

            if top_ranked:
                content.is_rag = True
                content.evidence_outcome = "retrieved"
                context_parts = []
                citations = []
                for idx, r in enumerate(top_ranked):
                    payload = r["payload"]
                    filename = payload.get("document") or payload.get("filename") or "Unknown"
                    page = (
                        payload.get("page")
                        if payload.get("page") is not None
                        else (
                            payload.get("page_number")
                            if payload.get("page_number") is not None
                            else "N/A"
                        )
                    )
                    score = r["hybrid_score"]

                    context_parts.append(
                        f"[Document: {filename} | Page: {page} | Citation Index: {idx + 1}]\n"
                        f"{r['text']}\n"
                    )

                    citations.append(
                        {
                            "filename": filename,
                            "page": page,
                            "document_id": payload.get("document_id"),
                            "chunk_id": r["id"],
                            "similarity_score": round(score, 3),
                            "text": r["text"],
                        }
                    )
                    content.chunks_used.append(r["id"])

                content.rag_context = "\n".join(context_parts)
                content.source_citations = citations
                content.rag_diagnostics = {
                    "query": query,
                    "vector_hits": [
                        {
                            "chunk_id": h["id"],
                            "score": round(h["score"], 3),
                            "filename": h["payload"].get("document")
                            or h["payload"].get("filename")
                            or "",
                        }
                        for h in vector_results[:5]
                    ],
                    "bm25_hits": [
                        {
                            "chunk_id": h["id"],
                            "score": round(h["score"], 3),
                            "filename": h["payload"].get("document")
                            or h["payload"].get("filename")
                            or "",
                        }
                        for h in bm25_results[:5]
                    ],
                    "selected_chunks": [
                        {
                            "chunk_id": c["id"],
                            "hybrid_score": round(c["hybrid_score"], 3),
                            "vector_score": round(c["vector_score"], 3),
                            "bm25_score": round(c["bm25_score"], 3),
                            "filename": c["payload"].get("document")
                            or c["payload"].get("filename")
                            or "",
                            "page": c["payload"].get("page")
                            if c["payload"].get("page") is not None
                            else (
                                c["payload"].get("page_number")
                                if c["payload"].get("page_number") is not None
                                else ""
                            ),
                        }
                        for c in top_ranked
                    ],
                    "final_context_passed_to_llm": content.rag_context,
                    "retrieval_latency_ms": round(
                        vector_latency + keyword_latency + emb_latency, 2
                    ),
                    "ranking_latency_ms": round(ranking_latency, 2),
                    "total_rag_latency_ms": round(total_rag_latency, 2),
                }
                return content

        # Answers come only from the learner's notes: without matching passages, refuse.
        content.evidence_outcome = "no_source" if document_id in (None, "none") else "insufficient"
        return content

    def topic_content(self, subject, topic, difficulty, topics) -> RetrievedContent:
        """Chosen topics' own slides as source material, in place of search results."""
        from sentio.study.topics import MAX_PRACTICE_TEXT, fit_pages

        content = RetrievedContent(
            subject=subject,
            topic=topic,
            difficulty=Difficulty(difficulty),
            learning_state="neutral",
            strategy=tutor_cfg.STRATEGY_MAP.get("neutral", "standard"),
            is_rag=True,
            evidence_outcome="retrieved",
        )
        parts = []
        for chosen in topics:
            for page, passage in fit_pages(chosen["pages"], MAX_PRACTICE_TEXT // len(topics)):
                index = len(content.source_citations) + 1
                parts.append(
                    f"[Document: {chosen['filename']} | Citation Index: {index} | "
                    f"Topic: {chosen['title']}]\n{passage}\n"
                )
                content.source_citations.append(
                    {
                        "filename": chosen["filename"],
                        "page": page,
                        "document_id": chosen["document_id"],
                        "chunk_id": None,
                        "similarity_score": 1.0,
                        "text": passage,
                        "topic_id": chosen["id"],
                        "topic": chosen["title"],
                    }
                )
        content.rag_context = "\n".join(parts)
        return content

    def get_tone_instruction(self, learning_state: str) -> str:
        strategy = tutor_cfg.STRATEGY_MAP.get(learning_state, "standard")
        return self.adapter.get_tone(strategy)
