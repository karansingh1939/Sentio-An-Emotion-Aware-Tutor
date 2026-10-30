"""Topics from slide/page headings, question attribution and topic states."""

from sentio.study.topics import (
    attribute,
    build_topics,
    fit_pages,
    is_weak,
    locate,
    place,
    topic_state,
)


def test_slides_with_the_same_title_form_one_topic():
    pages = [
        (1, "Paging\nMemory is split into frames."),
        (2, "Paging (cont.)\nA page table maps pages to frames."),
        (3, "Segmentation\nSegments have variable size."),
        (4, "Segments are described by a base and a limit."),  # no heading: continues
        (5, "Summary"),
    ]
    assert build_topics(pages, "lecture") == [
        {"title": "Paging", "first_page": 1, "last_page": 2},
        {"title": "Segmentation", "first_page": 3, "last_page": 4},
        {"title": "Summary", "first_page": 5, "last_page": 5},
    ]


def test_continued_titles_and_opening_sentences_extend_the_current_topic():
    pages = [
        (1, "Periodic Signal\nA signal that repeats."),
        (2, "Periodic Signal–Continued\nIts period is T."),
        (3, "Peak value: The maximum value of a function as\nit varies over time."),
        (4, "Consider the figure. When compared to f(t), the wave\nis shifted."),
        (5, "RMS Value\nThe effective value."),
        (6, "RMS Value…Continued\nSquare root of the mean square."),
    ]
    assert [(t["title"], t["first_page"], t["last_page"]) for t in build_topics(pages, "x")] == [
        ("Periodic Signal", 1, 4),
        ("RMS Value", 5, 6),
    ]


def test_running_headers_and_page_numbers_are_not_topics():
    pages = [
        (n, f"CS301 Operating Systems\n{n}\n{title}\nBody text.")
        for n, title in enumerate(["Processes", "Processes", "Threads", "Threads", "Deadlock"], 1)
    ]
    assert [t["title"] for t in build_topics(pages, "x")] == ["Processes", "Threads", "Deadlock"]


def test_single_page_notes_become_one_topic_named_by_their_heading_or_file():
    assert build_topics([(1, "Thermodynamics\nHeat is energy in transfer.")], "notes") == [
        {"title": "Thermodynamics", "first_page": 1, "last_page": 1}
    ]
    assert build_topics([(1, "Heat is energy in transfer.")], "notes")[0]["title"] == "notes"
    assert build_topics([(1, "   ")], "notes") == []


def test_questions_are_attributed_to_the_best_matching_passage():
    citations = [
        {"document_id": "d1", "page": 2, "text": "A page table maps pages to frames."},
        {"document_id": "d1", "page": 5, "text": "Deadlock needs circular wait and hold and wait."},
    ]
    question = {
        "question_text": "Which condition is required for deadlock?",
        "correct_answer": "Circular wait",
        "explanation": "Deadlock needs circular wait.",
    }
    assert attribute(question, citations) == ("d1", 5)
    assert attribute({"question_text": "Unrelated?"}, citations) == (None, None)
    assert attribute(question, [{"page": 5, "text": "circular wait deadlock"}]) == (None, None)


def test_topic_states_follow_the_ready_bar():
    assert topic_state([])["state"] == "not_started"
    assert topic_state([True, True])["state"] == "practising"
    assert topic_state([False, True, True, True])["state"] == "ready"
    late_slip = topic_state([True, True, True, True, False])
    assert late_slip == {
        "state": "practising",
        "answers": 5,
        "recent_correct": 2,
        "recent_total": 3,
    }
    assert is_weak(late_slip)
    assert not is_weak(topic_state([True, True]))


def test_real_deck_layouts_cover_questions_abbreviations_subheadings_and_closing():
    pages = [
        (1, "Computer Networks\nCourse code: NET101\nWeek 2\nRouting"),
        (2, "What is a Router?\nA router forwards packets."),
        (3, "Static vs. Dynamic Routing\nTables are fixed or learned."),
        (4, "Routing Table\nEach entry maps a prefix to a next hop."),
        (5, "Routing Table- Example\nA default route catches the rest."),
        (6, "Link-state Protocols\nRouters flood link states."),
        (7, "Link State Protocols\nDijkstra computes paths."),
        (8, "Thank You"),
    ]
    assert [(t["title"], t["first_page"], t["last_page"]) for t in build_topics(pages, "x")] == [
        ("What is a Router?", 2, 2),
        ("Static vs. Dynamic Routing", 3, 3),
        ("Routing Table", 4, 5),
        ("Link-state Protocols", 6, 7),
    ]


CITATIONS = [
    {
        "document_id": "d1",
        "page": 2,
        "text": "A page table maps pages to frames.",
        "topic": "Paging",
    },
    {"document_id": "d1", "page": 5, "text": "Deadlock needs circular wait.", "topic": "Deadlock"},
]
DEADLOCK = {"question_text": "What does deadlock need?", "correct_answer": "Circular wait"}


def test_a_named_passage_is_kept_when_it_shares_words_with_the_question():
    assert locate({**DEADLOCK, "source": 2}, CITATIONS) == (CITATIONS[1], "model")
    assert place(CITATIONS[1]) == ("d1", 5)
    assert place(None) == (None, None)


def test_a_wrong_or_missing_passage_falls_back_to_word_overlap():
    for source in (None, 0, 3, 1):
        assert locate({**DEADLOCK, "source": source}, CITATIONS) == (CITATIONS[1], "overlap")
    assert locate({"question_text": "Unrelated?"}, CITATIONS) == (None, "none")


def test_a_named_passage_far_weaker_than_the_best_match_is_not_believed():
    citations = [
        {"document_id": "d1", "page": 1, "text": "Memory uses frames."},
        {"document_id": "d1", "page": 2, "text": "Deadlock needs circular wait and hold."},
    ]
    question = {"question_text": "Does deadlock need circular wait and memory?"}
    assert locate({**question, "source": 1}, citations) == (citations[1], "overlap")
    close = {"question_text": "Does memory deadlock?"}
    assert locate({**close, "source": 1}, citations) == (citations[0], "model")


def test_a_question_asked_for_a_topic_stays_in_it():
    paging = CITATIONS[:1]
    assert locate({"question_text": "Unrelated?"}, CITATIONS, paging) == (paging[0], "topic")
    assert locate(DEADLOCK, CITATIONS, paging) == (paging[0], "topic")
    assert locate({**DEADLOCK, "source": 2}, CITATIONS, paging) == (CITATIONS[1], "model")


def test_long_topics_are_sampled_evenly_within_the_budget():
    pages = [(n, "x" * 100) for n in range(1, 11)]
    assert fit_pages(pages, 5000) == pages
    fitted = fit_pages(pages, 500)
    assert [page for page, _ in fitted] == [1, 3, 5, 7, 9]
    assert [(page, len(text)) for page, text in fit_pages([(1, "x" * 900)], 300)] == [(1, 300)]
    uneven = fit_pages([(1, "x" * 900), (2, "y" * 100)], 500)
    assert sum(len(text) for _, text in uneven) <= 500
