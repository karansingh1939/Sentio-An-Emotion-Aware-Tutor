from typing import List, Optional

from sentio.persistence.session_repository import SessionPersister


class DocumentRepository:
    """
    Repository for managing curriculum document and chunk persistence operations.
    Decoupled from SessionManager to resolve circular dependencies.
    """

    def __init__(self, persister: Optional[SessionPersister] = None):
        self.persister = persister or SessionPersister()

    def load(self):
        self.persister.load()

    def list_documents(self, student_id: Optional[str] = None) -> List[dict]:
        return self.persister.list_documents(student_id=student_id)

    def get_all_chunks(self, student_id: Optional[str] = None) -> List[dict]:
        return self.persister.get_all_chunks(student_id=student_id)

    def register_document(self, doc: dict) -> bool:
        return self.persister.register_document(doc)

    def delete_document(self, doc_id: str) -> bool:
        return self.persister.delete_document(doc_id)

    def save_document_chunks(self, doc_id: str, chunks: List[dict]) -> bool:
        return self.persister.save_document_chunks(doc_id, chunks)

    def get_document_chunks(self, doc_id: str) -> List[dict]:
        return self.persister.get_document_chunks(doc_id)

    def replace(self, document, chunks, require_owner=False):
        from sqlalchemy import text

        with self.persister._engine.begin() as connection:
            connection.exec_driver_sql("BEGIN IMMEDIATE")
            if (
                require_owner
                and not connection.execute(
                    text("SELECT student_id FROM student_accounts WHERE student_id=:owner"),
                    {"owner": document["student_id"]},
                ).first()
            ):
                raise PermissionError("Learner account is no longer available.")
            if not self.persister.register_document(document, connection=connection):
                raise RuntimeError("Document metadata could not be saved.")
            if not self.persister.save_document_chunks(
                document["id"], chunks, connection=connection
            ):
                raise RuntimeError("Document text could not be saved.")

    def remove(self, document_id):
        from sqlalchemy import text

        with self.persister._engine.begin() as connection:
            connection.execute(
                text("DELETE FROM document_chunks WHERE document_id=:id"), {"id": document_id}
            )
            connection.execute(text("DELETE FROM documents WHERE id=:id"), {"id": document_id})

    def preview(self, document_id, owner, limit=20, offset=0):
        from sqlalchemy import text

        with self.persister._engine.connect() as connection:
            document = (
                connection.execute(
                    text(
                        "SELECT id,filename,extraction_method FROM documents WHERE id=:id AND student_id=:owner"
                    ),
                    {"id": document_id, "owner": owner},
                )
                .mappings()
                .first()
            )
            if not document:
                return None
            chunks = (
                connection.execute(
                    text(
                        "SELECT page_number,chunk_index,text_content FROM document_chunks WHERE document_id=:id ORDER BY chunk_index LIMIT :limit OFFSET :offset"
                    ),
                    {"id": document_id, "limit": limit, "offset": offset},
                )
                .mappings()
                .all()
            )
            total = connection.execute(
                text("SELECT COUNT(*) FROM document_chunks WHERE document_id=:id"),
                {"id": document_id},
            ).scalar()
        return {
            "document": dict(document),
            "chunks": [dict(c) for c in chunks],
            "total": total,
            "offset": offset,
            "next_offset": offset + len(chunks) if offset + len(chunks) < total else None,
        }

    def clear_all_documents_and_chunks(self) -> bool:
        return self.persister.clear_all_documents_and_chunks()

    def get_document_by_checksum(
        self, checksum: str, student_id: Optional[str] = None
    ) -> Optional[dict]:
        return self.persister.get_document_by_checksum(checksum, student_id=student_id)

    def get_document_by_filename(
        self, filename: str, student_id: Optional[str] = None, category: Optional[str] = None
    ) -> Optional[dict]:
        return self.persister.get_document_by_filename(
            filename, student_id=student_id, category=category
        )
