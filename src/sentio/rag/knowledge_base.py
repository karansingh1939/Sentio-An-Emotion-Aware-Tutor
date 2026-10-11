"""
knowledge_base.py — Curriculum Knowledge Base for Emotion-Aware AI Tutor
=========================================================================
Responsibilities:
  1. Store structured curriculum content (concepts, explanations, examples,
     analogies, quizzes) per subject and difficulty level
  2. Retrieve the best content chunk for a given topic + learning state
  3. Adapt difficulty dynamically based on student performance
  4. Support semantic search using sentence embeddings (RAG-lite)
  5. Track which content has been shown to avoid repetition

Architecture:
  ┌─────────────────────────────────────────────────────────┐
  │  KnowledgeBase                                          │
  │   ├── CurriculumStore   (static structured content)     │
  │   ├── SemanticRetriever (embedding-based search)        │
  │   └── ContentAdapter    (strategy → content transform)  │
  └─────────────────────────────────────────────────────────┘

Usage:
    kb = KnowledgeBase()
    kb.load()

    chunk = kb.retrieve(
        subject="mathematics",
        topic="derivatives",
        difficulty="intermediate",
        learning_state="struggling"
    )
    print(chunk.explanation)
    print(chunk.analogy)
"""

import hashlib
import json
import logging
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from sentio.config import DATA_DIR, nlp_cfg, tutor_cfg

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


class ContentType(str, Enum):
    CONCEPT = "concept"  # Core definition / theory
    EXPLANATION = "explanation"  # Detailed walkthrough
    ANALOGY = "analogy"  # Real-world comparison
    EXAMPLE = "example"  # Worked example
    QUIZ = "quiz"  # Comprehension check question
    CHALLENGE = "challenge"  # Harder extension problem
    MOTIVATION = "motivation"  # Why this matters (real-world hook)
    HINT = "hint"  # Step-by-step nudge


# ─────────────────────────────────────────────
# DATA CLASSES
# ─────────────────────────────────────────────


@dataclass
class ContentChunk:
    """
    A single retrievable piece of curriculum content.
    Every chunk is tagged with subject, topic, difficulty, and type.
    """

    chunk_id: str
    subject: str
    topic: str
    difficulty: Difficulty
    content_type: ContentType
    text: str  # The actual content text
    tags: List[str] = field(default_factory=list)
    prerequisites: List[str] = field(default_factory=list)
    follow_ups: List[str] = field(default_factory=list)
    embedding: Optional[np.ndarray] = field(default=None, repr=False)

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("embedding")  # Don't serialize numpy arrays
        return d

    @staticmethod
    def make_id(subject: str, topic: str, difficulty: str, content_type: str) -> str:
        raw = f"{subject}::{topic}::{difficulty}::{content_type}"
        return hashlib.md5(raw.encode()).hexdigest()[:12]


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

    concept: Optional[str] = None
    explanation: Optional[str] = None
    analogy: Optional[str] = None
    example: Optional[str] = None
    quiz_question: Optional[str] = None
    challenge: Optional[str] = None
    motivation: Optional[str] = None
    hints: List[str] = field(default_factory=list)

    # Metadata
    chunks_used: List[str] = field(default_factory=list)  # chunk_ids

    # RAG dynamic fields
    source_citations: List[dict] = field(default_factory=list)
    rag_diagnostics: Dict[str, Any] = field(default_factory=dict)
    is_rag: bool = False
    rag_context: Optional[str] = None

    def has_content(self) -> bool:
        return any(
            [
                self.concept,
                self.explanation,
                self.analogy,
                self.example,
                self.quiz_question,
                self.is_rag and self.rag_context,
            ]
        )


# ─────────────────────────────────────────────
# CURRICULUM STORE
# ─────────────────────────────────────────────


class CurriculumStore:
    """
    In-memory store of all curriculum ContentChunks.
    Seeded with built-in content; can also load from JSON files.
    """

    def __init__(self):
        self._chunks: Dict[str, ContentChunk] = {}  # chunk_id → chunk
        self._index: Dict[str, List[str]] = {}  # "subject::topic::diff" → [ids]

    # ── Loading ────────────────────────────────

    def seed_builtin(self):
        """Load the built-in curriculum (hardcoded seed data)."""
        for chunk_data in _BUILTIN_CURRICULUM:
            chunk = ContentChunk(**chunk_data)
            self.add(chunk)
        logger.info(f"Seeded {len(self._chunks)} built-in content chunks.")

    def load_from_file(self, path: Path):
        """Load additional curriculum from a JSON file."""
        if not path.exists():
            logger.warning(f"Curriculum file not found: {path}")
            return
        with open(path) as f:
            data = json.load(f)
        for item in data:
            self.add(ContentChunk(**item))
        logger.info(f"Loaded {len(data)} chunks from {path}")

    def save_to_file(self, path: Path):
        """Persist all chunks to JSON."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump([c.to_dict() for c in self._chunks.values()], f, indent=2)
        logger.info(f"Saved {len(self._chunks)} chunks → {path}")

    # ── CRUD ───────────────────────────────────

    def add(self, chunk: ContentChunk):
        self._chunks[chunk.chunk_id] = chunk
        key = f"{chunk.subject}::{chunk.topic}::{chunk.difficulty}"
        self._index.setdefault(key, []).append(chunk.chunk_id)

    def get(self, chunk_id: str) -> Optional[ContentChunk]:
        return self._chunks.get(chunk_id)

    def query(
        self,
        subject: str,
        topic: str,
        difficulty: Difficulty,
        content_types: Optional[List[ContentType]] = None,
    ) -> List[ContentChunk]:
        """Retrieve all chunks matching subject + topic + difficulty."""
        key = f"{subject}::{topic}::{difficulty}"
        ids = self._index.get(key, [])
        chunks = [self._chunks[i] for i in ids if i in self._chunks]
        if content_types:
            chunks = [c for c in chunks if c.content_type in content_types]
        return chunks

    def all_topics(self, subject: str) -> List[str]:
        """List all topics available for a subject."""
        topics = set()
        for key in self._index:
            parts = key.split("::")
            if parts[0] == subject:
                topics.add(parts[1])
        return sorted(topics)

    def __len__(self):
        return len(self._chunks)


# ─────────────────────────────────────────────
# SEMANTIC RETRIEVER
# ─────────────────────────────────────────────


class SemanticRetriever:
    """
    Embedding-based semantic search over ContentChunks.
    Uses sentence-transformers for dense retrieval (RAG-lite).
    Falls back to keyword matching if model unavailable.
    """

    def __init__(self, model_name: str = nlp_cfg.EMBEDDING_MODEL):
        self.model_name = model_name
        self._model = None
        self._chunk_ids: List[str] = []
        self._embeddings: Optional[np.ndarray] = None

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

    def index(self, chunks: List[ContentChunk]):
        """Build embedding index from a list of chunks."""
        self._load_model()
        if not self._model:
            return

        texts = [c.text for c in chunks]
        self._chunk_ids = [c.chunk_id for c in chunks]
        self._embeddings = self._model.encode(
            texts, batch_size=32, show_progress_bar=False, normalize_embeddings=True
        )
        logger.info(f"Indexed {len(chunks)} chunks for semantic search.")

    def search(self, query: str, chunks: List[ContentChunk], top_k: int = 5) -> List[ContentChunk]:
        """
        Return top-k semantically similar chunks for a query.
        Falls back to simple keyword overlap if embeddings unavailable.
        """
        self._load_model()

        if self._model is None or self._embeddings is None:
            return self._keyword_fallback(query, chunks, top_k)

        query_emb = self._model.encode([query], normalize_embeddings=True)
        # Cosine similarity (embeddings are L2-normalized → dot product)
        scores = (self._embeddings @ query_emb.T).flatten()
        top_indices = np.argsort(scores)[::-1][:top_k]
        return [chunks[i] for i in top_indices]

    def _keyword_fallback(
        self, query: str, chunks: List[ContentChunk], top_k: int
    ) -> List[ContentChunk]:
        """Simple word-overlap scoring when embeddings aren't available."""
        query_words = set(query.lower().split())
        scored = []
        for chunk in chunks:
            chunk_words = set(chunk.text.lower().split())
            overlap = len(query_words & chunk_words)
            scored.append((overlap, chunk))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [c for _, c in scored[:top_k]]


# ─────────────────────────────────────────────
# CONTENT ADAPTER
# ─────────────────────────────────────────────


class ContentAdapter:
    """
    Given a teaching strategy (from TutorConfig.STRATEGY_MAP),
    decides WHICH content types to prioritize and HOW to frame them.
    """

    # Strategy → ordered list of preferred content types
    STRATEGY_CONTENT_PRIORITY: Dict[str, List[ContentType]] = {
        "challenge": [ContentType.CHALLENGE, ContentType.EXAMPLE, ContentType.QUIZ],
        "standard": [ContentType.EXPLANATION, ContentType.EXAMPLE, ContentType.QUIZ],
        "explore": [
            ContentType.CONCEPT,
            ContentType.EXPLANATION,
            ContentType.MOTIVATION,
            ContentType.CHALLENGE,
        ],
        "simplify": [
            ContentType.ANALOGY,
            ContentType.HINT,
            ContentType.EXAMPLE,
            ContentType.EXPLANATION,
        ],
        "reassure": [ContentType.HINT, ContentType.ANALOGY, ContentType.EXAMPLE],
        "reframe": [ContentType.ANALOGY, ContentType.MOTIVATION, ContentType.EXPLANATION],
        "motivate": [ContentType.MOTIVATION, ContentType.EXAMPLE, ContentType.ANALOGY],
    }

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

    def get_priority_types(self, strategy: str) -> List[ContentType]:
        return self.STRATEGY_CONTENT_PRIORITY.get(
            strategy, [ContentType.EXPLANATION, ContentType.EXAMPLE]
        )

    def get_tone(self, strategy: str) -> str:
        return self.STRATEGY_TONE.get(strategy, "Explain clearly and helpfully.")

    def adapt_difficulty(
        self,
        current: Difficulty,
        learning_state: str,
        consecutive_correct: int,
        consecutive_wrong: int,
    ) -> Difficulty:
        """
        Decide if difficulty should change based on performance signals.

        Rules:
          - 3+ correct in a row + engaged/curious → step up
          - 2+ wrong in a row + struggling/anxious → step down
          - frustrated → step down (reduce cognitive load)
        """
        if consecutive_correct >= 3 and learning_state in ("engaged", "curious"):
            new = current.step_up()
            if new != current:
                logger.info(f"Difficulty UP: {current} → {new}")
            return new

        if consecutive_wrong >= 2 or learning_state in ("struggling", "anxious"):
            new = current.step_down()
            if new != current:
                logger.info(f"Difficulty DOWN: {current} → {new}")
            return new

        if learning_state == "frustrated":
            return current.step_down()

        return current


# ─────────────────────────────────────────────
# KNOWLEDGE BASE (Facade)
# ─────────────────────────────────────────────


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

    CURRICULUM_FILE = DATA_DIR / "curriculum.json"

    def __init__(
        self,
        store: Optional[CurriculumStore] = None,
        retriever: Optional[SemanticRetriever] = None,
        adapter: Optional[ContentAdapter] = None,
        vdb: Optional[Any] = None,
        doc_repo: Optional[Any] = None,
        ranker: Optional[Any] = None,
    ):
        self.store = store or CurriculumStore()
        self.retriever = retriever or SemanticRetriever()
        self.adapter = adapter or ContentAdapter()
        self._shown: Dict[str, set] = {}  # session_id → {chunk_ids seen}

        # Connect to SQLite Document registry and Qdrant client
        from sentio.rag.reranker import HybridRanker
        from sentio.rag.vector_db import QdrantVectorDB
        from sentio.repositories.document_repository import DocumentRepository

        self.vdb = vdb or QdrantVectorDB()
        self.doc_repo = doc_repo or DocumentRepository()
        self.ranker = ranker or HybridRanker(w_vector=0.75, w_keyword=0.25)

    def load(self):
        """Load built-in curriculum + any user-added JSON curriculum."""
        self.store.seed_builtin()
        self.store.load_from_file(self.CURRICULUM_FILE)
        self.doc_repo.load()
        self.vdb.connect()
        logger.info(f"KnowledgeBase ready. Total chunks: {len(self.store)}")

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
                subj_chunks = [c for c in all_db_chunks if c.get("subject") == subject]
                if not subj_chunks:
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

            # 4. Merge candidates and back-fill scores
            merged_hits = {}
            db_chunk_map = {c["chunk_id"]: c for c in subj_chunks}

            for hit in vector_results:
                if hit["score"] < 0.35:
                    continue
                cid = hit["id"]
                if cid not in db_chunk_map:
                    continue
                text_content = db_chunk_map[cid]["text_content"]
                merged_hits[cid] = {
                    "id": cid,
                    "text": text_content,
                    "payload": db_chunk_map[cid],
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
                    hit["bm25_score"] = self._compute_single_bm25_score(bm25_searcher, query, cid)

            # 5. Hybrid Reranking Pass
            t_rank_start = time.perf_counter()
            top_ranked = self.ranker.rerank(query, list(merged_hits.values()), limit=5)
            t_rank_end = time.perf_counter()
            ranking_latency = (t_rank_end - t_rank_start) * 1000

            total_rag_latency = (time.perf_counter() - t_rag_start) * 1000

            if top_ranked:
                content.is_rag = True
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

        # Fallback to static curriculum
        priority_types = self.adapter.get_priority_types(strategy)
        chunks = self.store.query(subject, topic, diff)

        if not chunks:
            for fallback_diff in [
                Difficulty.INTERMEDIATE,
                Difficulty.BEGINNER,
                Difficulty.ADVANCED,
            ]:
                chunks = self.store.query(subject, topic, fallback_diff)
                if chunks:
                    break

        if query and chunks:
            chunks = self.retriever.search(query, chunks, top_k=min(10, len(chunks)))

        seen = self._shown.get(session_id, set()) if session_id else set()
        fresh = [c for c in chunks if c.chunk_id not in seen]
        if not fresh:
            fresh = chunks

        type_map = {c.content_type: c for c in fresh}

        for ct in priority_types:
            chunk = type_map.get(ct)
            if not chunk:
                continue
            self._assign_content(content, ct, chunk.text)
            content.chunks_used.append(chunk.chunk_id)
            if session_id:
                self._shown.setdefault(session_id, set()).add(chunk.chunk_id)

        return content

    def _compute_single_bm25_score(self, searcher, query: str, doc_id: str) -> float:
        """Compute BM25 score of a single document ID for a query."""
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

    def _assign_content(self, content: RetrievedContent, ct: ContentType, text: str):
        """Map ContentType → RetrievedContent field."""
        mapping = {
            ContentType.CONCEPT: "concept",
            ContentType.EXPLANATION: "explanation",
            ContentType.ANALOGY: "analogy",
            ContentType.EXAMPLE: "example",
            ContentType.QUIZ: "quiz_question",
            ContentType.CHALLENGE: "challenge",
            ContentType.MOTIVATION: "motivation",
            ContentType.HINT: "hints",
        }
        attr = mapping.get(ct)
        if attr == "hints":
            content.hints.append(text)
        elif attr:
            setattr(content, attr, text)

    def adapt_difficulty(
        self,
        current_difficulty: str,
        learning_state: str,
        consecutive_correct: int = 0,
        consecutive_wrong: int = 0,
    ) -> str:
        """Proxy to ContentAdapter.adapt_difficulty."""
        result = self.adapter.adapt_difficulty(
            Difficulty(current_difficulty), learning_state, consecutive_correct, consecutive_wrong
        )
        return result.value

    def list_topics(self, subject: str) -> List[str]:
        return self.store.all_topics(subject)

    def get_tone_instruction(self, learning_state: str) -> str:
        strategy = tutor_cfg.STRATEGY_MAP.get(learning_state, "standard")
        return self.adapter.get_tone(strategy)

    def reset_session(self, session_id: str):
        """Clear shown-content history for a session."""
        self._shown.pop(session_id, None)


# ─────────────────────────────────────────────
# BUILT-IN CURRICULUM SEED DATA
# ─────────────────────────────────────────────
# Format: matches ContentChunk fields (without embedding)
# Covers: mathematics (derivatives), physics (newton's laws),
#         computer_science (recursion) across all 3 difficulty levels.
# Add more topics by extending this list or loading curriculum.json.


def _make_chunk(
    subject, topic, difficulty, content_type, text, tags=None, prereqs=None, followups=None
):
    cid = ContentChunk.make_id(subject, topic, difficulty, content_type)
    return {
        "chunk_id": cid,
        "subject": subject,
        "topic": topic,
        "difficulty": Difficulty(difficulty),
        "content_type": ContentType(content_type),
        "text": text,
        "tags": tags or [],
        "prerequisites": prereqs or [],
        "follow_ups": followups or [],
    }


_BUILTIN_CURRICULUM = [
    # ══════════════════════════════════════
    # MATHEMATICS — DERIVATIVES
    # ══════════════════════════════════════
    _make_chunk(
        "mathematics",
        "derivatives",
        "beginner",
        "concept",
        "A derivative measures how fast something changes. If you have a function f(x), "
        "its derivative f'(x) tells you the slope of the curve at any point x — "
        "in other words, how steeply the function is rising or falling.",
        tags=["calculus", "rate-of-change", "slope"],
    ),
    _make_chunk(
        "mathematics",
        "derivatives",
        "beginner",
        "analogy",
        "Imagine you're driving a car and watching your speedometer. "
        "Your position is the function; your speed at any moment is the derivative. "
        "The derivative doesn't tell you where you are — it tells you how fast you're moving.",
        tags=["analogy", "speed", "intuition"],
    ),
    _make_chunk(
        "mathematics",
        "derivatives",
        "beginner",
        "example",
        "Let's differentiate f(x) = x².\n"
        "Using the power rule: bring the exponent down and reduce it by 1.\n"
        "  f'(x) = 2x¹ = 2x\n"
        "This means at x=3, the slope is 2×3 = 6. The curve is rising steeply there.",
        tags=["power-rule", "worked-example"],
    ),
    _make_chunk(
        "mathematics",
        "derivatives",
        "beginner",
        "quiz",
        "Quick check: What is the derivative of f(x) = x³? "
        "Use the power rule. What does f'(2) equal?",
        tags=["quiz", "power-rule"],
    ),
    _make_chunk(
        "mathematics",
        "derivatives",
        "beginner",
        "motivation",
        "Derivatives power everything from GPS navigation (optimizing routes) "
        "to machine learning (gradient descent updates model weights using derivatives). "
        "Every neural network you've heard of — GPT, Stable Diffusion — relies on derivatives.",
        tags=["motivation", "real-world", "ML"],
    ),
    _make_chunk(
        "mathematics",
        "derivatives",
        "beginner",
        "hint",
        "Stuck? Remember the power rule: d/dx [xⁿ] = n·xⁿ⁻¹. "
        "Just multiply by the exponent, then lower the exponent by 1.",
        tags=["hint", "power-rule"],
    ),
    _make_chunk(
        "mathematics",
        "derivatives",
        "intermediate",
        "concept",
        "The chain rule lets you differentiate composite functions: if h(x) = f(g(x)), "
        "then h'(x) = f'(g(x)) · g'(x). You differentiate the outer function (leaving the "
        "inner alone), then multiply by the derivative of the inner function.",
        tags=["chain-rule", "composite-functions"],
    ),
    _make_chunk(
        "mathematics",
        "derivatives",
        "intermediate",
        "analogy",
        "Think of the chain rule like gears. If gear A turns gear B, and gear B turns gear C, "
        "the speed of C depends on both gear ratios multiplied together. "
        "Each link in the chain contributes a factor.",
        tags=["chain-rule", "analogy", "gears"],
    ),
    _make_chunk(
        "mathematics",
        "derivatives",
        "intermediate",
        "example",
        "Differentiate h(x) = sin(x²).\n"
        "  Outer function: f(u) = sin(u) → f'(u) = cos(u)\n"
        "  Inner function: g(x) = x²   → g'(x) = 2x\n"
        "  Chain rule:  h'(x) = cos(x²) · 2x = 2x·cos(x²)",
        tags=["chain-rule", "trig", "worked-example"],
    ),
    _make_chunk(
        "mathematics",
        "derivatives",
        "intermediate",
        "quiz",
        "Using the chain rule, differentiate h(x) = (3x + 1)⁵. What is h'(x)?",
        tags=["quiz", "chain-rule"],
    ),
    _make_chunk(
        "mathematics",
        "derivatives",
        "advanced",
        "concept",
        "Implicit differentiation handles equations where y cannot be easily isolated. "
        "Differentiate both sides with respect to x, treating y as a function of x, "
        "and apply the chain rule whenever you differentiate a y term (multiply by dy/dx).",
        tags=["implicit-differentiation", "advanced"],
    ),
    _make_chunk(
        "mathematics",
        "derivatives",
        "advanced",
        "example",
        "Find dy/dx for the circle x² + y² = 25.\n"
        "  Differentiate both sides w.r.t. x:\n"
        "    2x + 2y·(dy/dx) = 0\n"
        "  Solve for dy/dx:\n"
        "    dy/dx = -x/y\n"
        "At point (3, 4): slope = -3/4.",
        tags=["implicit", "circle", "worked-example"],
    ),
    _make_chunk(
        "mathematics",
        "derivatives",
        "advanced",
        "challenge",
        "Challenge: Use implicit differentiation to find dy/dx for "
        "x³ + y³ = 6xy (the folium of Descartes). "
        "Then find the slope at the point (3, 3).",
        tags=["challenge", "implicit", "folium"],
    ),
    # ══════════════════════════════════════
    # PHYSICS — NEWTON'S LAWS
    # ══════════════════════════════════════
    _make_chunk(
        "physics",
        "newtons_laws",
        "beginner",
        "concept",
        "Newton's Three Laws of Motion:\n"
        "1. Inertia: An object stays at rest or in uniform motion unless acted on by a force.\n"
        "2. F = ma: Force equals mass times acceleration.\n"
        "3. Action-Reaction: For every action, there is an equal and opposite reaction.",
        tags=["newton", "laws-of-motion", "forces"],
    ),
    _make_chunk(
        "physics",
        "newtons_laws",
        "beginner",
        "analogy",
        "Law 1 — A hockey puck on ice keeps sliding forever because there's almost no friction. "
        "Law 2 — Pushing an empty shopping cart (low mass) gives huge acceleration; "
        "a full one needs much more force. "
        "Law 3 — When you jump, you push the Earth down; the Earth pushes you up.",
        tags=["analogy", "inertia", "everyday"],
    ),
    _make_chunk(
        "physics",
        "newtons_laws",
        "beginner",
        "example",
        "A 10 kg box is pushed with a force of 50 N. Find its acceleration.\n"
        "  F = ma  →  a = F/m = 50/10 = 5 m/s²\n"
        "The box accelerates at 5 metres per second squared.",
        tags=["F=ma", "worked-example", "calculation"],
    ),
    _make_chunk(
        "physics",
        "newtons_laws",
        "beginner",
        "motivation",
        "Newton's laws explain how rockets launch (Law 3), "
        "how seatbelts save lives (Law 1 — your body keeps moving in a crash), "
        "and how athletes optimize performance. Every engineering structure uses these laws.",
        tags=["motivation", "rockets", "engineering"],
    ),
    _make_chunk(
        "physics",
        "newtons_laws",
        "intermediate",
        "concept",
        "Free body diagrams (FBDs) show all forces acting on an object as arrows. "
        "Normal force acts perpendicular to surfaces; friction acts parallel (opposing motion); "
        "gravity acts downward. Net force = vector sum of all forces → use F_net = ma.",
        tags=["free-body-diagram", "normal-force", "friction"],
    ),
    _make_chunk(
        "physics",
        "newtons_laws",
        "intermediate",
        "example",
        "A 5 kg block slides down a 30° frictionless incline. Find its acceleration.\n"
        "  Component of gravity along incline: F = mg·sin(30°) = 5×10×0.5 = 25 N\n"
        "  a = F/m = 25/5 = 5 m/s²\n"
        "It accelerates at 5 m/s² down the slope.",
        tags=["incline", "components", "worked-example"],
    ),
    _make_chunk(
        "physics",
        "newtons_laws",
        "advanced",
        "concept",
        "In non-inertial (accelerating) reference frames, we introduce pseudo-forces "
        "(e.g. centrifugal force, Coriolis force) to apply Newton's laws. "
        "These are fictitious — they don't exist in an inertial frame — but they're "
        "mathematically useful (e.g., weather systems, Foucault pendulum).",
        tags=["non-inertial", "pseudo-forces", "reference-frames"],
    ),
    _make_chunk(
        "physics",
        "newtons_laws",
        "advanced",
        "challenge",
        "Challenge: A 2 kg block sits on top of a 5 kg block on a frictionless surface. "
        "The coefficient of static friction between the blocks is 0.4. "
        "What is the maximum force F that can be applied to the lower block "
        "without the upper block sliding? Draw the FBD first.",
        tags=["challenge", "friction", "system-of-blocks"],
    ),
    # ══════════════════════════════════════
    # COMPUTER SCIENCE — RECURSION
    # ══════════════════════════════════════
    _make_chunk(
        "computer_science",
        "recursion",
        "beginner",
        "concept",
        "Recursion is when a function calls itself to solve a smaller version of the same problem. "
        "Every recursive function needs: (1) a base case — the stopping condition, "
        "and (2) a recursive case — the function calling itself with a simpler input.",
        tags=["recursion", "base-case", "call-stack"],
    ),
    _make_chunk(
        "computer_science",
        "recursion",
        "beginner",
        "analogy",
        "Think of Russian nesting dolls (Matryoshka). To find the smallest doll, "
        "you open the current one and check if there's another inside — "
        "you keep going until you find one that doesn't open (base case). "
        "That's exactly how recursion works.",
        tags=["analogy", "matryoshka", "intuition"],
    ),
    _make_chunk(
        "computer_science",
        "recursion",
        "beginner",
        "example",
        "Factorial using recursion:\n\n"
        "def factorial(n):\n"
        "    if n == 0:          # base case\n"
        "        return 1\n"
        "    return n * factorial(n - 1)  # recursive case\n\n"
        "factorial(4) → 4 × factorial(3) → 4 × 3 × factorial(2) → ... → 24",
        tags=["factorial", "python", "worked-example"],
    ),
    _make_chunk(
        "computer_science",
        "recursion",
        "beginner",
        "quiz",
        "What is the output of factorial(5)? Trace through the calls step by step to verify.",
        tags=["quiz", "factorial", "trace"],
    ),
    _make_chunk(
        "computer_science",
        "recursion",
        "beginner",
        "hint",
        "If your recursive function never stops, check: does your base case cover all "
        "stopping conditions? Is the recursive call always moving toward the base case "
        "(i.e., is n getting smaller)?",
        tags=["hint", "infinite-recursion", "debugging"],
    ),
    _make_chunk(
        "computer_science",
        "recursion",
        "intermediate",
        "concept",
        "The call stack stores each recursive call's local variables and return address. "
        "Deep recursion can cause a stack overflow. "
        "Tail recursion (last operation is the recursive call) can be optimized by "
        "compilers to avoid stack growth. Python does NOT optimize tail calls by default.",
        tags=["call-stack", "tail-recursion", "stack-overflow"],
    ),
    _make_chunk(
        "computer_science",
        "recursion",
        "intermediate",
        "example",
        "Binary search using recursion:\n\n"
        "def binary_search(arr, target, lo, hi):\n"
        "    if lo > hi:\n"
        "        return -1\n"
        "    mid = (lo + hi) // 2\n"
        "    if arr[mid] == target:\n"
        "        return mid\n"
        "    elif arr[mid] < target:\n"
        "        return binary_search(arr, target, mid+1, hi)\n"
        "    else:\n"
        "        return binary_search(arr, target, lo, mid-1)",
        tags=["binary-search", "divide-conquer", "python"],
    ),
    _make_chunk(
        "computer_science",
        "recursion",
        "advanced",
        "concept",
        "Memoization caches recursive results to avoid redundant computation. "
        "Dynamic programming (bottom-up) replaces recursion with iteration + a table. "
        "Both reduce exponential time complexity (e.g., naive Fibonacci O(2^n)) "
        "to polynomial (O(n)).",
        tags=["memoization", "dynamic-programming", "optimization"],
    ),
    _make_chunk(
        "computer_science",
        "recursion",
        "advanced",
        "challenge",
        "Challenge: Implement the Tower of Hanoi for n disks recursively. "
        "Then prove that the minimum number of moves is 2ⁿ - 1. "
        "Finally, convert your recursive solution to an iterative one.",
        tags=["hanoi", "challenge", "proof", "iterative"],
    ),
    # ══════════════════════════════════════
    # MATHEMATICS — LIMITS
    # ══════════════════════════════════════
    _make_chunk(
        "mathematics",
        "limits",
        "beginner",
        "concept",
        "A limit describes what value a function approaches as the input gets "
        "closer and closer to some value — even if the function never actually reaches it. "
        "Written as: lim(x→a) f(x) = L means f(x) gets arbitrarily close to L as x→a.",
        tags=["limits", "calculus", "approach"],
    ),
    _make_chunk(
        "mathematics",
        "limits",
        "beginner",
        "analogy",
        "Imagine walking toward a wall. You can get closer and closer — "
        "1 metre away, 10 cm, 1 mm — without ever touching it. "
        "The wall is the limit: the value you're approaching, not necessarily reaching.",
        tags=["analogy", "approach", "intuition"],
    ),
    _make_chunk(
        "mathematics",
        "limits",
        "intermediate",
        "concept",
        "L'Hôpital's Rule: If lim f(x)/g(x) gives 0/0 or ∞/∞ (indeterminate form), "
        "then lim f(x)/g(x) = lim f'(x)/g'(x), provided the latter limit exists. "
        "Differentiate numerator and denominator separately — not as a quotient.",
        tags=["lhopital", "indeterminate", "technique"],
    ),
]
