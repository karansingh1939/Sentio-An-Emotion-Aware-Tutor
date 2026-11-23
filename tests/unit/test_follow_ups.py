"""A follow-up is searched in the context of the conversation's topic, without phrase lists."""

from types import SimpleNamespace

from sentio.tutor.difficulty import asks_for_another_explanation
from sentio.tutor.search import merge_rankings, search_text, stands_alone


def passage(chunk, page, text="x"):
    return {"chunk_id": chunk, "filename": "notes.pdf", "page": page, "text": text}


def found(*citations, outcome="retrieved"):
    return SimpleNamespace(
        evidence_outcome=outcome,
        source_citations=list(citations),
        rag_context="",
        chunks_used=[],
    )


def test_didnt_understand_asks_for_another_explanation():
    assert asks_for_another_explanation("no i didnt understand")
    assert not asks_for_another_explanation("What does understand mean in NLP?")


def test_repeated_padding_counts_once_and_the_query_is_capped():
    # E18: a question followed by the same sentence a hundred times.
    padded = "Please explain what a convolution is. " + "I need this for my exam. " * 100
    assert search_text(padded) == "Please explain what a convolution is. I need this for my exam."
    assert len(search_text("word " * 500).split()) == 60


def test_a_vague_follow_up_keeps_the_topics_slides_on_top():
    # "which one is better?" alone finds noise; joined to the topic it finds the slides.
    alone = found(passage("noise", 4))
    joined = found(passage("edge", 8), passage("cloud", 6))
    merged = merge_rankings(alone, joined)
    # Equal ranks tie; the topic-joined order breaks the tie.
    assert [c["chunk_id"] for c in merged.source_citations] == ["edge", "noise", "cloud"]
    assert not stands_alone(alone, joined, merged)


def test_a_follow_up_that_finds_nothing_alone_uses_the_topic_search():
    # "I still don't get it" alone retrieves nothing and used to be refused.
    alone = found(outcome="insufficient")
    joined = found(passage("grades", 3))
    merged = merge_rankings(alone, joined)
    assert merged.source_citations[0]["chunk_id"] == "grades"
    assert not stands_alone(alone, joined, merged)


def test_a_new_question_becomes_the_topic():
    alone = found(passage("csv", 4), passage("tabular", 3))
    joined = found(passage("csv", 4), passage("grades", 3))
    merged = merge_rankings(alone, joined)
    assert merged.source_citations[0]["chunk_id"] == "csv"
    assert stands_alone(alone, joined, merged)


def test_nothing_found_by_either_search_stays_a_refusal():
    alone = found(outcome="insufficient")
    joined = found(outcome="insufficient")
    assert merge_rankings(alone, joined) is alone
