"""Owner-scoped slides (pages) of a lecture, with the topic each belongs to.

Phase 4 contract stub: the backend engineer implements this (docs/project/phase-4-slide-study.md).
"""


class SlideRepository:
    def __init__(self, engine):
        self.engine = engine

    def slides(self, owner, document_id):
        """{"document_id", "filename", "slides": [...]}, or None."""
        raise NotImplementedError("Phase 4: SlideRepository.slides")

    def slide(self, owner, document_id, number):
        """One slide with "filename" and "document_id", or None."""
        raise NotImplementedError("Phase 4: SlideRepository.slide")
