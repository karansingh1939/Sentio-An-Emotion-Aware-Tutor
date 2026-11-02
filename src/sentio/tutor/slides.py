"""Explaining one lecture slide: the slide first, then nearby passages from the lecture."""

from sentio.config import tutor_cfg
from sentio.rag.knowledge_base import Difficulty, RetrievedContent
from sentio.study.topics import MAX_PRACTICE_TEXT

MAX_NEARBY = 3

SLIDE_INSTRUCTION = (
    "The student is studying one lecture slide: the first source passage. "
    "Explain what the slide says, why it matters, and one small example supported by the "
    "passages. Answer follow-up questions from the slide first, then from the other passages. "
    "When the slide and passages do not cover something, say so plainly. "
    "Cite as above, copying the passage's reference exactly. "
)


def slide_content(kb, subject, topic, difficulty, slide, nearby=()):
    """RetrievedContent with the slide as Citation Index 1, then up to 3 nearby passages."""
    content = RetrievedContent(
        subject=subject,
        topic=topic,
        difficulty=Difficulty(difficulty),
        learning_state="neutral",
        strategy=tutor_cfg.STRATEGY_MAP.get("neutral", "standard"),
        is_rag=True,
        evidence_outcome="retrieved",
        rag_diagnostics={"slide": slide["number"], "document_id": slide["document_id"]},
    )
    first = {
        "filename": slide["filename"],
        "page": slide["number"],
        "document_id": slide["document_id"],
        "chunk_id": None,
        "similarity_score": 1.0,
        "text": _slide_text(slide),
        "topic_id": slide.get("topic_id"),
        "topic": slide.get("topic_title"),
    }
    others = [
        citation
        for citation in nearby
        if citation.get("document_id") == slide["document_id"]
        and citation.get("page") != slide["number"]
        and (citation.get("text") or "").strip()
    ]
    parts = []
    for index, citation in enumerate([first, *others[:MAX_NEARBY]], 1):
        # Only the slide number here: a "Page:" field got confused with the Citation Index.
        parts.append(
            f"[Document: {citation['filename']} | Citation Index: {index} | "
            f"Slide: {citation['page']}]\n{citation['text']}\n"
        )
        content.source_citations.append(citation)
        if citation.get("chunk_id"):
            content.chunks_used.append(citation["chunk_id"])
    content.rag_context = "\n".join(parts)
    return content


def _slide_text(slide):
    """The slide's text, led by its title when the text does not already include it."""
    text = (slide.get("text") or "").strip()
    title = (slide.get("title") or "").strip()
    if title and title not in text:
        text = f"{title}\n{text}"
    return text[:MAX_PRACTICE_TEXT]
