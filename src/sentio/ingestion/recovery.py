"""Recoverable file publication; SQL decides which document revision is active."""

import hashlib
import json
import logging
import time
import uuid
from pathlib import Path
from threading import RLock

from sqlalchemy import text

from sentio.repositories.documents import DocumentRepository

logger = logging.getLogger(__name__)


class DocumentRecovery:
    def __init__(self, persister, vectors, root, require_owner=True):
        self.engine = persister._engine
        self.repository = DocumentRepository(persister)
        self.vectors = vectors
        self.root = Path(root).resolve()
        self.lock = RLock()
        self.require_owner = require_owner

    def path(self, value, owner):
        owner_path = self.root / owner
        lexical = Path(value).absolute()
        if not lexical.is_relative_to(owner_path) or any(
            part.is_symlink() or (hasattr(part, "is_junction") and part.is_junction())
            for part in (lexical, *lexical.parents)
            if part == owner_path or part.is_relative_to(owner_path)
        ):
            raise ValueError(
                "Document recovery path is outside the learner directory or uses a link."
            )
        candidate = Path(value).resolve()
        owned = owner_path.resolve()
        if (
            owned == self.root
            or not owned.is_relative_to(self.root)
            or not candidate.is_relative_to(owned)
            or candidate == owned
        ):
            raise ValueError("Document recovery path is outside the learner directory.")
        return candidate

    def _start(self, owner, kind, payload):
        operation = str(uuid.uuid4())
        backup = self.path(self.root / owner / ".recovery" / (operation + ".bak"), owner)
        backup.parent.mkdir(parents=True, exist_ok=True)
        payload["backup"] = str(backup)
        destination = self.path(payload["destination"], owner)
        payload["previous_file_hash"] = (
            self.file_hash(destination) if destination.exists() else None
        )
        payload["previous_checksum"] = self.active_checksum(payload["document_id"], owner)
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO recovery_operations (operation_id,student_id,kind,payload_json,status,created_at) VALUES (:id,:owner,:kind,:payload,'pending',:now)"
                ),
                {
                    "id": operation,
                    "owner": owner,
                    "kind": kind,
                    "payload": json.dumps(payload),
                    "now": time.time(),
                },
            )
        return operation, backup

    def _state(self, operation, status, error=None):
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE recovery_operations SET status=:status,error=:error WHERE operation_id=:id"
                ),
                {"id": operation, "status": status, "error": error},
            )
        if status in ("completed", "failed"):
            self.prune()

    def prune(self):
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    "DELETE FROM recovery_operations WHERE status IN ('completed','done','failed') AND created_at<:cutoff"
                ),
                {"cutoff": time.time() - 7 * 86400},
            )
            connection.execute(
                text("""DELETE FROM recovery_operations WHERE operation_id IN (
                SELECT operation_id FROM (
                    SELECT operation_id, ROW_NUMBER() OVER (
                        PARTITION BY student_id ORDER BY created_at DESC,operation_id DESC) AS position
                    FROM recovery_operations WHERE status IN ('completed','done','failed'))
                WHERE position>500)""")
            )

    def replace(self, pending, destination, document, chunks, old_chunks):
        owner = document["student_id"]
        pending = self.path(pending, owner)
        destination = self.path(destination, owner)
        new_ids = {c["chunk_id"] for c in chunks}
        payload = {
            "document_id": document["id"],
            "checksum": document["checksum"],
            "destination": str(destination),
            "had_file": destination.exists(),
            "old_chunk_ids": [c["chunk_id"] for c in old_chunks if c["chunk_id"] not in new_ids],
        }
        with self.lock:
            if self.require_owner:
                for existing in self.repository.list_documents(student_id=owner):
                    if (
                        existing["category"] == document["category"]
                        and existing["filename"].casefold() == document["filename"].casefold()
                        and existing["id"] != document["id"]
                    ):
                        raise ValueError(
                            "A document with this filename already exists; match its capitalization."
                        )
                with self.engine.connect() as connection:
                    if not connection.execute(
                        text("SELECT 1 FROM student_accounts WHERE student_id=:owner"),
                        {"owner": owner},
                    ).scalar():
                        raise PermissionError("Learner account is no longer available.")
            operation, backup = self._start(owner, "replace", payload)
            try:
                if destination.exists():
                    destination.replace(backup)
                pending.replace(destination)
                self.repository.replace(document, chunks, require_owner=self.require_owner)
            except Exception:
                try:
                    self._rollback(payload, owner)
                    self._state(
                        operation,
                        "failed",
                        "Publication failed; the previous document was restored.",
                    )
                except Exception:
                    logger.exception("Document publication requires startup recovery")
                raise
            self._cleanup(operation, payload, owner)

    def delete(self, document, destination, chunks):
        owner = document["student_id"]
        destination = self.path(destination, owner)
        payload = {
            "document_id": document["id"],
            "destination": str(destination),
            "had_file": destination.exists(),
            "old_chunk_ids": [c["chunk_id"] for c in chunks],
        }
        with self.lock:
            operation, backup = self._start(owner, "delete", payload)
            try:
                if destination.exists():
                    destination.replace(backup)
                self.repository.remove(document["id"])
            except Exception:
                try:
                    self._rollback(payload, owner)
                    self._state(operation, "failed", "Deletion failed; the document was restored.")
                except Exception:
                    logger.exception("Document deletion requires startup recovery")
                raise
            return self._cleanup(operation, payload, owner)

    def _rollback(self, payload, owner):
        destination = self.path(payload["destination"], owner)
        backup = self.path(payload["backup"], owner)
        if backup.exists():
            backup.replace(destination)
        elif not payload["had_file"]:
            destination.unlink(missing_ok=True)
        elif (
            not destination.exists() or self.file_hash(destination) != payload["previous_file_hash"]
        ):
            raise RuntimeError("The original file is missing; recovery needs the saved backup.")

    def _cleanup(self, operation, payload, owner):
        # Inactive IDs cannot be retrieved, even if Qdrant cleanup is unavailable.
        try:
            self.path(payload["backup"], owner).unlink(missing_ok=True)
            with self.engine.connect() as connection:
                active_ids = set(
                    connection.execute(text("SELECT chunk_id FROM document_chunks")).scalars()
                )
            inactive = [cid for cid in payload["old_chunk_ids"] if cid not in active_ids]
            if not self.vectors.delete_chunk_points(inactive):
                self._state(
                    operation,
                    "cleanup_pending",
                    "Inactive vectors will be removed when retrieval is available.",
                )
                return False
            self._state(operation, "completed")
            return True
        except Exception:
            logger.exception("Document cleanup remains pending")
            self._state(operation, "cleanup_pending", "Cleanup will retry at startup.")
            return False

    def recover(self, owner=None):
        self.prune()
        recovered, pending = 0, 0
        with self.lock:
            with self.engine.connect() as connection:
                query = "SELECT * FROM recovery_operations WHERE status IN ('pending','cleanup_pending')"
                if owner:
                    query += " AND student_id=:owner"
                rows = connection.execute(text(query), {"owner": owner}).mappings().all()
            for row in rows:
                try:
                    payload = json.loads(row["payload_json"])
                    if row["kind"] not in ("replace", "delete"):
                        raise ValueError("Unknown document recovery operation")
                    current = self.active_checksum(payload["document_id"], row["student_id"])
                    committed = (
                        row["status"] == "cleanup_pending"
                        or (row["kind"] == "delete" and current is None)
                        or (row["kind"] == "replace" and current == payload["checksum"])
                    )
                    superseded = current != payload["previous_checksum"]
                    if committed or superseded:
                        cleaned = self._cleanup(row["operation_id"], payload, row["student_id"])
                        recovered += int(cleaned)
                        pending += int(not cleaned)
                    else:
                        self._rollback(payload, row["student_id"])
                        self._state(
                            row["operation_id"],
                            "failed",
                            "Interrupted operation rolled back. Retry explicitly.",
                        )
                        recovered += 1
                except Exception:
                    pending += 1
                    logger.exception("Could not recover document operation %s", row["operation_id"])
            return {"recovered": recovered, "pending": pending}

    def active_checksum(self, document_id, owner):
        with self.engine.connect() as connection:
            return connection.execute(
                text("SELECT checksum FROM documents WHERE id=:id AND student_id=:owner"),
                {"id": document_id, "owner": owner},
            ).scalar()

    @staticmethod
    def file_hash(path):
        with Path(path).open("rb") as source:
            return hashlib.file_digest(source, "sha256").hexdigest()
