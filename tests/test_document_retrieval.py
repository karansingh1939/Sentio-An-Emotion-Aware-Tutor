import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from sentio.api.app import app
from sentio.ingestion.pipeline import DocumentIngestionPipeline
from sentio.rag.bm25 import BM25Searcher
from sentio.rag.reranker import HybridRanker
from sentio.rag.vector_db import QdrantVectorDB
from sentio.session.session_manager import SessionManager

# Enforce configurations for testing
from tests.helpers import login_student


class TestSentioPhaseC(unittest.TestCase):
    """
    Test suite verifying Phase C upgrades: Source-Aware RAG,
    BM25 keyword search, Hybrid reranker, Ingestion, and document endpoints.
    """

    @classmethod
    def setUpClass(cls):
        # Create directories for testing
        cls.docs_root = Path("data/documents")
        for cat in ["textbooks", "notes", "assignments", "reference", "uploaded"]:
            (cls.docs_root / cat).mkdir(parents=True, exist_ok=True)

    def setUp(self):
        # Clean up global agent and ensure it's not loaded
        from sentio.api.app import agent as global_agent

        global_agent.sm._sessions.clear()
        global_agent.sm._diagnostics.clear()
        global_agent._loaded = False

        # Delete old test DB if exists
        db_path = Path("data/test_tutor_sessions.db")
        if db_path.exists():
            try:
                db_path.unlink()
            except Exception:
                pass

        # Initialize SQLite database
        self.sm = SessionManager()
        self.sm.load()

        # Initialize in-memory Qdrant DB
        self.vdb = QdrantVectorDB()
        self.vdb.connect()
        self.vdb.create_collection_if_not_exists(vector_size=384)

        # Clear document registry tables
        self.sm.clear_all_documents_and_chunks()

    def tearDown(self):
        # Clear test database
        db_path = Path("test_tutor_sessions.db")
        if db_path.exists():
            try:
                db_path.unlink()
            except Exception:
                pass

        # Remove uploaded test files
        uploaded_dir = self.docs_root / "uploaded"
        if uploaded_dir.exists():
            for f in uploaded_dir.glob("*"):
                try:
                    f.unlink()
                except Exception:
                    pass

    def test_bm25_keyword_searcher(self):
        """Verify BM25 keyword search indexes and ranks terms correctly."""
        chunks = [
            {
                "id": "chunk_1",
                "text_content": "Calculus limits are the foundation of derivatives.",
                "subject": "mathematics",
            },
            {
                "id": "chunk_2",
                "text_content": "Newtonian physics is governed by three laws of motion.",
                "subject": "physics",
            },
            {
                "id": "chunk_3",
                "text_content": "Recursive algorithms call themselves to solve smaller problems.",
                "subject": "computer_science",
            },
        ]

        searcher = BM25Searcher()
        searcher.index(chunks)

        # Search for limit
        hits = searcher.search("limits", limit=3)
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["id"], "chunk_1")

        # Search for motion laws
        hits = searcher.search("motion laws", limit=3)
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["id"], "chunk_2")

    def test_hybrid_score_fusion_ranker(self):
        """Verify HybridRanker normalizes and merges Vector and BM25 scores."""
        hits = [
            {
                "id": "c1",
                "text": "Limits are cool",
                "payload": {"document": "calc.txt"},
                "vector_score": 0.85,
                "bm25_score": 1.5,
            },
            {
                "id": "c2",
                "text": "Derivatives are slopes",
                "payload": {"document": "calc.txt"},
                "vector_score": 0.60,
                "bm25_score": 5.0,
            },
        ]

        # 0.75 Vector + 0.25 BM25
        ranker = HybridRanker(w_vector=0.75, w_keyword=0.25)
        top = ranker.rerank("query", hits, limit=2)

        self.assertEqual(len(top), 2)
        # c2 has maximum BM25 (scaled to 1.0) and vector 0.60
        # c1 has maximum Vector (scaled to 1.0) and BM25 1.5 (scaled to 0.0)
        # c1 hybrid score = 0.75 * 1.0 + 0.25 * 0.0 = 0.75
        # c2 hybrid score = 0.75 * 0.0 + 0.25 * 1.0 = 0.25 (when min-max range is active)
        # Let's verify c1 is ranked first
        self.assertEqual(top[0]["id"], "c1")
        self.assertAlmostEqual(top[0]["hybrid_score"], 0.75, places=2)
        self.assertAlmostEqual(top[1]["hybrid_score"], 0.25, places=2)

    def test_document_ingestion_pipeline(self):
        """Verify incremental text document indexing, duplicate checks, and Qdrant population."""
        pipeline = DocumentIngestionPipeline(sm=self.sm, vdb=self.vdb)

        # Write temporary note
        uploaded_dir = self.docs_root / "uploaded"
        temp_file = uploaded_dir / "test_notes_c.txt"
        with open(temp_file, "w", encoding="utf-8") as f:
            f.write("Limits explain what value a function approaches near a point.")

        # Index document
        success = pipeline.process_file(temp_file, "uploaded", "mathematics")
        self.assertTrue(success)

        # Check database registration
        docs = self.sm.list_documents()
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0]["filename"], "test_notes_c.txt")
        self.assertEqual(docs[0]["status"], "indexed")
        self.assertEqual(docs[0]["chunk_count"], 1)

        # Check chunks in DB
        chunks = self.sm.get_document_chunks(docs[0]["id"])
        self.assertEqual(len(chunks), 1)
        self.assertIn("approaches near a point", chunks[0]["text_content"])

        # Incremental check: Syncing unmodified file should skip processing
        duration_report = pipeline.scan_and_sync(subject_map={"test_notes_c.txt": "mathematics"})
        self.assertTrue(duration_report["skipped_count"] >= 1)

        # Pruning check: Delete file, run sync, record must be deleted
        temp_file.unlink()
        duration_report = pipeline.scan_and_sync()
        self.assertEqual(duration_report["deleted_count"], 1)

        docs_after = self.sm.list_documents()
        filenames = [d["filename"] for d in docs_after]
        self.assertNotIn("test_notes_c.txt", filenames)

    def test_fastapi_document_endpoints(self):
        """Verify FastAPI REST endpoints for document upload, listing, deletion, and sync."""
        with TestClient(app) as client:
            login_student(client, admin=True)
            # 1. Upload a text file
            file_data = {
                "file": (
                    "student_guide.txt",
                    b"F=ma is the formula for Newtons second law of motion.",
                    "text/plain",
                )
            }
            resp_upload = client.post(
                "/api/v1/documents/upload",
                files=file_data,
                data={"category": "uploaded", "subject": "physics"},
            )
            self.assertEqual(resp_upload.status_code, 201)
            up_data = resp_upload.json()
            self.assertTrue(up_data["indexed"])
            self.assertEqual(up_data["filename"], "student_guide.txt")

            # 2. List documents
            resp_list = client.get("/api/v1/documents")
            self.assertEqual(resp_list.status_code, 200)
            list_data = resp_list.json()
            self.assertEqual(list_data["count"], 1)
            doc_id = list_data["documents"][0]["id"]
            self.assertEqual(list_data["documents"][0]["filename"], "student_guide.txt")
            self.assertEqual(list_data["documents"][0]["status"], "indexed")

            # 3. Synchronize documents
            resp_sync = client.post("/api/v1/documents/sync")
            self.assertEqual(resp_sync.status_code, 200)
            sync_data = resp_sync.json()
            self.assertTrue(sync_data["synced"])

            # 4. Delete document
            resp_delete = client.delete(f"/api/v1/documents/{doc_id}")
            self.assertEqual(resp_delete.status_code, 200)
            self.assertTrue(resp_delete.json()["deleted"])

            # 5. Verify deleted from list
            resp_list_after = client.get("/api/v1/documents")
            filenames_after = [d["filename"] for d in resp_list_after.json()["documents"]]
            self.assertNotIn("student_guide.txt", filenames_after)


if __name__ == "__main__":
    unittest.main()
