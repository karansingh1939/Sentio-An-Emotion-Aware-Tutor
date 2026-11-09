"""Explaining a slide cites the slide first, then a few other passages from the same lecture."""

from sentio.ai.grounding import validate_references
from sentio.tutor.slides import SLIDE_INSTRUCTION, slide_content

SLIDE = {
    "number": 4,
    "title": "Paging",
    "text": "Paging splits memory into fixed size frames.",
    "topic_id": "topic-1",
    "topic_title": "Paging",
    "filename": "memory.pptx",
    "document_id": "doc-1",
}


def _passage(page, text="A page table maps each page to a frame.", document="doc-1", chunk=None):
    return {
        "filename": "memory.pptx" if document == "doc-1" else "other.pdf",
        "page": page,
        "document_id": document,
        "chunk_id": chunk or f"chunk-{page}",
        "similarity_score": 0.5,
        "text": text,
    }


def _content(nearby=()):
    return slide_content(None, "os", "Paging", "beginner", SLIDE, nearby)


def test_the_slide_is_citation_one_with_its_slide_number():
    content = _content()
    assert (content.is_rag, content.evidence_outcome) == (True, "retrieved")
    assert content.rag_context.startswith(
        "[Document: memory.pptx | Citation Index: 1 | Slide: 4]\n"
        "Paging splits memory into fixed size frames."
    )
    assert "Page:" not in content.rag_context
    [citation] = content.source_citations
    assert (citation["page"], citation["document_id"], citation["topic"]) == (4, "doc-1", "Paging")
    validate_references("Memory is split into frames [memory.pptx Page 4].", content)


def test_up_to_three_nearby_passages_from_the_same_lecture_follow():
    nearby = [
        _passage(4, "Another chunk of the same slide."),  # Already the slide.
        _passage(5, "   "),  # Nothing to cite.
        _passage(6, document="doc-2"),  # Another document.
        _passage(7),
        _passage(8),
        _passage(9),
        _passage(10),
    ]
    content = _content(nearby)
    assert [c["page"] for c in content.source_citations] == [4, 7, 8, 9]
    assert "Citation Index: 4 | Slide: 9]" in content.rag_context
    assert "Slide: 10" not in content.rag_context
    assert content.chunks_used == ["chunk-7", "chunk-8", "chunk-9"]


def test_the_title_leads_when_the_text_lacks_it():
    content = slide_content(None, "os", "x", "beginner", {**SLIDE, "title": "Frames"})
    assert content.source_citations[0]["text"].startswith("Frames\nPaging splits")
    assert _content().source_citations[0]["text"] == SLIDE["text"]


def test_the_instruction_is_short_and_plain():
    for rule in ("why it matters", "example", "slide first", "say so plainly", "reference"):
        assert rule in SLIDE_INSTRUCTION
    assert len(SLIDE_INSTRUCTION) < 500
