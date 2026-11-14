from types import SimpleNamespace

from sentio.rag.knowledge_base import KEYWORD_INDEXES_KEPT, KnowledgeBase


def knowledge_base():
    stub = SimpleNamespace()
    return KnowledgeBase(retriever=stub, vdb=stub, doc_repo=stub)


def rows(text="An external net force changes motion.", filename="forces.txt"):
    # Fresh dicts each call, as a new SQLite read returns.
    return [
        {"chunk_id": "c1", "document_id": "d1", "text_content": text, "filename": filename},
        {"chunk_id": "c2", "document_id": "d1", "text_content": "Heat flows from hot to cold."},
    ]


def test_unchanged_chunks_reuse_one_index():
    kb = knowledge_base()
    first = kb._keyword_index(rows())
    assert kb._keyword_index(rows()) is first
    assert first.search("force")[0]["id"] == "c1"


def test_edited_text_gets_a_fresh_index_that_finds_the_new_words():
    kb = knowledge_base()
    old = kb._keyword_index(rows())
    new = kb._keyword_index(rows(text="Momentum is mass times velocity."))
    assert new is not old
    assert new.search("force") == []
    assert new.search("momentum")[0]["id"] == "c1"


def test_a_renamed_file_gets_a_fresh_index_with_the_new_name():
    kb = knowledge_base()
    kb._keyword_index(rows())
    renamed = kb._keyword_index(rows(filename="lecture-1.txt"))
    assert renamed.search("force")[0]["payload"]["filename"] == "lecture-1.txt"


def test_a_removed_chunk_gets_a_fresh_index_without_it():
    kb = knowledge_base()
    kb._keyword_index(rows())
    assert kb._keyword_index(rows()[:1]).search("heat") == []


def test_only_recent_selections_are_kept():
    kb = knowledge_base()
    first = kb._keyword_index(rows(text="selection 0"))
    for number in range(1, KEYWORD_INDEXES_KEPT + 1):
        kb._keyword_index(rows(text=f"selection {number}"))
    assert len(kb._keyword_indexes) == KEYWORD_INDEXES_KEPT
    assert kb._keyword_index(rows(text="selection 0")) is not first
