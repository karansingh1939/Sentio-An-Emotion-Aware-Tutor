"""Owner-scoped slides (pages) of a lecture, with the topic each belongs to."""

from sqlalchemy import text

from sentio.repositories.topics import TopicRepository

MAX_TITLE_CHARS = 120


def _first_line(content):
    for line in content.splitlines():
        if line.strip():
            return line.strip()[:MAX_TITLE_CHARS]
    return ""


class SlideRepository:
    def __init__(self, engine):
        self.engine = engine

    def _pages(self, owner, document_id):
        """(filename, [(page, text)]) of an indexed document the owner has, else None."""
        with self.engine.connect() as connection:
            document = connection.execute(
                text(
                    "SELECT filename FROM documents WHERE id=:id AND student_id=:owner AND status='indexed'"
                ),
                {"id": document_id, "owner": owner},
            ).first()
            if document is None:
                return None
            pages = {}
            for page, content in connection.execute(
                text(
                    "SELECT COALESCE(page_number,1),text_content FROM document_chunks WHERE document_id=:id ORDER BY 1,chunk_index"
                ),
                {"id": document_id},
            ):
                pages.setdefault(page, []).append(content)
        return document[0], [(page, "\n".join(parts)) for page, parts in sorted(pages.items())]

    def slides(self, owner, document_id):
        """{"document_id", "filename", "slides": [...]}, or None."""
        found = self._pages(owner, document_id)
        lecture = TopicRepository(self.engine).document_topics(owner, document_id)
        if found is None or lecture is None:
            return None
        filename, pages = found
        slides = []
        for page, content in pages:
            if not content.strip():
                continue
            topic = next(
                (t for t in lecture["topics"] if t["first_page"] <= page <= t["last_page"]),
                None,
            )
            starts_topic = topic is not None and topic["first_page"] == page
            slides.append(
                {
                    "number": page,
                    "title": topic["title"] if starts_topic else _first_line(content),
                    "text": content,
                    "topic_id": topic["id"] if topic else None,
                    "topic_title": topic["title"] if topic else None,
                }
            )
        return {"document_id": document_id, "filename": filename, "slides": slides}

    def slide(self, owner, document_id, number):
        """One slide with "filename" and "document_id", or None."""
        lecture = self.slides(owner, document_id)
        if lecture is None:
            return None
        for slide in lecture["slides"]:
            if slide["number"] == number:
                return {**slide, "filename": lecture["filename"], "document_id": document_id}
        return None
