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
