from sentio.rag.bm25 import BM25Searcher, edit_distance
from sentio.rag.evidence_policy import has_relevance_signal

NOTES = [
    {"id": "limits", "text": "A derivative is the instantaneous rate of change of a function."},
    {"id": "forces", "text": "Uniform motion changes only when an external net force acts."},
    {"id": "circuits", "text": "Electric current is measured in amperes."},
]


def searcher():
    s = BM25Searcher()
    s.index(NOTES)
    return s


def test_edit_distance_counts_a_swap_of_neighbours_once():
    assert edit_distance("motoin", "motion", 1) == 1
    assert edit_distance("derivitive", "derivative", 2) == 1
    assert edit_distance("atlantis", "amperes", 2) == 3


def test_misspelled_words_find_the_notes_that_cover_them():
    s = searcher()
    for question, expected in [
        ("derivitive measures what", "limits"),
        ("wat changes uniform motoin", "forces"),
        ("unit of electric curent", "circuits"),
    ]:
        # The evidence gate only needs the covering note among the candidates. Keyword
        # scores alone can rank another note first ("measures" also corrects to the
        # circuits note's "measured"); the hybrid ranker's embeddings decide the order.
        assert expected in [hit["id"] for hit in s.search(s.correct_query(question))], question


def test_a_typo_in_the_only_shared_word_used_to_find_nothing():
    s = searcher()
    assert s.search("derivitive measures what") == []
    assert [hit["id"] for hit in s.search(s.correct_query("derivitive measures what"))]


def test_correction_keeps_the_original_word_and_ignores_short_words():
    s = searcher()
    assert s.correct_query("curent") == "curent current"
    # Four letters or fewer is too ambiguous to correct.
    assert s.correct_query("rat") == "rat"


def test_questions_the_notes_do_not_cover_stay_unmatched():
    s = searcher()
    for question in ["who is the pm of atlantis", "lottery numbers for tmrw"]:
        corrected = s.correct_query(question)
        assert corrected == " ".join(s._tokenize(question))
        # Keyword hits on "the" or "of" are dropped by the evidence gate.
        assert not any(has_relevance_signal(corrected, hit["text"]) for hit in s.search(corrected))
