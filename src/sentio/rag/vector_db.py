import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from qdrant_client import QdrantClient
    from qdrant_client.http import models
    from qdrant_client.http.exceptions import UnexpectedResponse

    HAS_QDRANT = True
except ImportError:
    HAS_QDRANT = False
    QdrantClient = None
    models = None
    UnexpectedResponse = Exception

logger = logging.getLogger(__name__)


class QdrantVectorDB:
    """
    Integrates Qdrant Vector Database for semantic search (RAG).
    Defaults to in-memory mode (':memory:') for easy local development and tests,
    with support for connecting to a local docker daemon if available.
    """

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        location: Optional[str] = None,
        mode: Optional[str] = None,
    ):
        from sentio.config import nlp_cfg

        self.mode = mode or os.getenv("QDRANT_MODE", nlp_cfg.QDRANT_MODE).lower().strip()
        self.host = host or nlp_cfg.QDRANT_HOST
        self.port = port or nlp_cfg.QDRANT_PORT
        self.location = location or (":memory:" if self.mode == "memory" else None)
        self.path = str(nlp_cfg.QDRANT_PATH)
        self.client: Optional[QdrantClient] = None
        self.collection_name = "curriculum_chunks"

    def is_available(self) -> bool:
        """Check if Qdrant client library is installed and client is successfully connected."""
        return HAS_QDRANT and self.client is not None

    def connect(self) -> bool:
        """Initialize the Qdrant client connection."""
        if self.client is not None:
            return True
        if not HAS_QDRANT:
            logger.warning(
                "qdrant-client package is not installed. Semantic vector search is disabled."
            )
            return False
        try:
            # Mode 1: External Qdrant server
            if self.mode == "server":
                try:
                    self.client = QdrantClient(host=self.host, port=self.port, timeout=3.0)
                    self.client.get_collections()
                    self.create_collection_if_not_exists()
                    logger.info(
                        f"Connected to external Qdrant server at http://{self.host}:{self.port}"
                    )
                    return True
                except Exception as e:
                    logger.warning(
                        f"Could not connect to Qdrant server at http://{self.host}:{self.port}: {e}. Falling back to local persistent disk storage."
                    )
                    self.mode = "local"

            # Mode 2: Local persistent disk storage (vectors survive application restarts)
            if self.mode == "local" or (self.location and self.location != ":memory:"):
                try:
                    db_dir = Path(self.path) if self.mode == "local" else Path(self.location)
                    db_dir.mkdir(parents=True, exist_ok=True)
                    self.client = QdrantClient(path=str(db_dir))
                    self.create_collection_if_not_exists()
                    logger.info(f"Initialized local persistent disk Qdrant client at {db_dir}")
                    return True
                except Exception as e:
                    logger.warning(
                        f"Could not open local disk Qdrant storage ({e}). Falling back to in-memory mode."
                    )

            # Mode 3: In-memory ephemeral mode (testing)
            self.client = QdrantClient(location=":memory:")
            self.create_collection_if_not_exists()
            logger.info("Initialized local in-memory Qdrant client.")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize Qdrant client: {e}")
            return False

    def create_collection_if_not_exists(self, vector_size: int = 384) -> bool:
        """Create a collection configured for sentence embeddings (384 dimensions by default)."""
        if not HAS_QDRANT:
            logger.warning("qdrant-client package is not installed. Skipping collection creation.")
            return False
        if not self.client:
            raise RuntimeError("QdrantClient is not connected. Call .connect() first.")

        try:
            # Check if collection exists
            collections = self.client.get_collections()
            collection_names = [col.name for col in collections.collections]

            if self.collection_name not in collection_names:
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=models.VectorParams(
                        size=vector_size, distance=models.Distance.COSINE
                    ),
                )
                logger.info(f"Created Qdrant collection: {self.collection_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to verify/create Qdrant collection: {e}")
            return False

    def index_chunks(
        self, ids: List[str], vectors: List[List[float]], payloads: List[Dict[str, Any]]
    ) -> bool:
        """Batch index chunks into Qdrant."""
        if not HAS_QDRANT:
            logger.warning("qdrant-client package is not installed. Skipping indexing.")
            return False
        if not self.client:
            raise RuntimeError("QdrantClient is not connected. Call .connect() first.")

        try:
            points = [
                models.PointStruct(
                    id=i,  # Expects numeric index or UUID string
                    vector=vector,
                    payload=payload,
                )
                for i, vector, payload in zip(ids, vectors, payloads)
            ]
            self.client.upsert(collection_name=self.collection_name, points=points)
            return True
        except Exception as e:
            logger.error(f"Upsert failed in Qdrant: {e}")
            return False

    def search(
        self,
        query_vector: List[float],
        limit: int = 5,
        filter_payload: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Perform similarity search with optional metadata payload filtering."""
        if not HAS_QDRANT:
            logger.warning("qdrant-client package is not installed. Skipping vector search.")
            return []
        if not self.client:
            raise RuntimeError("QdrantClient is not connected. Call .connect() first.")

        query_filter = None
        if filter_payload:
            must_filters = []
            for key, val in filter_payload.items():
                if isinstance(val, list):
                    must_filters.append(
                        models.FieldCondition(key=key, match=models.MatchAny(any=val))
                    )
                else:
                    must_filters.append(
                        models.FieldCondition(key=key, match=models.MatchValue(value=val))
                    )
            query_filter = models.Filter(must=must_filters)

        try:
            results = self.client.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                query_filter=query_filter,
                limit=limit,
            )
            # Reformat to simple python dictionaries
            return [
                {"id": res.id, "score": res.score, "payload": res.payload} for res in results.points
            ]
        except Exception as e:
            logger.error(f"Search failed in Qdrant: {e}")
            return []

    def delete_document_points(self, doc_id: str) -> bool:
        """Delete all points associated with a specific document ID from Qdrant."""
        if not HAS_QDRANT:
            logger.warning(
                "qdrant-client package is not installed. Skipping document points deletion."
            )
            return False
        if not self.client:
            raise RuntimeError("QdrantClient is not connected. Call .connect() first.")
        try:
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="document_id", match=models.MatchValue(value=doc_id)
                        )
                    ]
                ),
            )
            logger.info(f"Deleted points for document {doc_id} from Qdrant.")
            return True
        except Exception as e:
            logger.error(f"Failed to delete points for document {doc_id} from Qdrant: {e}")
            return False


# Smoke test/Benchmark runner
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    db = QdrantVectorDB()

    print("Testing connection...")
    if not db.connect():
        print(
            "Qdrant connection failed (or package not installed). Skipping remainder of script test."
        )
    else:
        print("Creating collection...")
        assert db.create_collection_if_not_exists(vector_size=3), "Failed to create collection"

        # Index a trial chunk and measure latency
        print("Indexing trial chunk...")
        t0 = time.perf_counter()
        trial_id = 1
        trial_vector = [0.1, 0.8, 0.1]
        trial_payload = {
            "text": "Derivatives measure rate of change",
            "subject": "mathematics",
            "topic": "derivatives",
        }

        success = db.index_chunks(ids=[trial_id], vectors=[trial_vector], payloads=[trial_payload])
        t_index = (time.perf_counter() - t0) * 1000
        print(f"Index status: {success} | Latency: {t_index:.2f} ms")
        assert success, "Index failed"
        assert t_index < 100.0, f"Indexing latency too high: {t_index:.2f} ms"

        # Perform a search check
        print("Searching trial chunk...")
        t1 = time.perf_counter()
        search_results = db.search(
            query_vector=[0.1, 0.8, 0.1], limit=1, filter_payload={"subject": "mathematics"}
        )
        t_search = (time.perf_counter() - t1) * 1000
        print(f"Search results: {search_results} | Latency: {t_search:.2f} ms")
        assert len(search_results) > 0, "No search results returned"
        assert search_results[0]["payload"]["topic"] == "derivatives", (
            "Incorrect payload topic retrieved"
        )

        print("\nAll Qdrant trials passed successfully!")
