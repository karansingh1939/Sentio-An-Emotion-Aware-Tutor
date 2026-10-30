"""Syllabus parsing, matching to lecture topics, and status rules."""

from sentio.study.syllabus import item_status, match, parse_syllabus, summarise

UNIVERSITY = """
CS301 Operating Systems        L T P C: 3 0 2 4
Course Objectives: understand how an operating system manages resources.
Unit I: Introduction – OS structure, system calls, processes (8 hours)
Unit II: Process Scheduling
1. FCFS and SJF scheduling
2. Round robin scheduling
3. Deadlocks; Banker's algorithm
UNIT-III Memory Management - Paging, Segmentation, Virtual memory.  10 Hours
Text Books:
1. Silberschatz, Operating System Concepts
Course Outcomes
CO1: Explain process scheduling.
"""


def test_units_and_topics_from_a_typical_university_syllabus():
    items = [(item["unit"], item["title"]) for item in parse_syllabus(UNIVERSITY)]
    assert items == [
        ("Unit I: Introduction", "OS structure"),
        ("Unit I: Introduction", "system calls"),
        ("Unit I: Introduction", "processes"),
        ("Unit II: Process Scheduling", "FCFS and SJF scheduling"),
        ("Unit II: Process Scheduling", "Round robin scheduling"),
        ("Unit II: Process Scheduling", "Deadlocks"),
        ("Unit II: Process Scheduling", "Banker's algorithm"),
        ("Unit III: Memory Management", "Paging"),
        ("Unit III: Memory Management", "Segmentation"),
        ("Unit III: Memory Management", "Virtual memory"),
    ]


def test_plain_bulleted_lists_without_units():
    text = "• Newton's laws of motion\n- Work, energy and power\n* Momentum\n12\n"
    assert [item["title"] for item in parse_syllabus(text)] == [
        "Newton's laws of motion",
        "Work",
        "energy and power",
        "Momentum",
    ]
    assert parse_syllabus("") == []


TOPICS = [
    {"id": "paging", "title": "Paging", "text": "Paging splits memory into frames."},
    {"id": "deadlock", "title": "Deadlock", "text": "Circular wait and hold and wait."},
    {"id": "rr", "title": "CPU Scheduling", "text": "Round robin gives each process a slice."},
]


def test_matching_uses_titles_first_then_slide_text():
    assert match("Paging", TOPICS) == ["paging"]
    assert match("Deadlocks", TOPICS) == ["deadlock"]  # plural
    assert match("Round robin scheduling", TOPICS) == ["rr"]
    assert match("Virtual memory", TOPICS) == []  # a gap: not in the notes
    assert match("Introduction", TOPICS) == []


def test_status_and_percentage():
    assert item_status([]) == "no_notes"
    assert item_status(["ready", "ready"]) == "ready"
    assert item_status(["not_started"]) == "not_started"
    assert item_status(["ready", "not_started"]) == "practising"
    assert summarise(["ready", "ready", "practising", "no_notes"]) == {
        "ready": 2,
        "review_due": 0,
        "practising": 1,
        "not_started": 0,
        "no_notes": 1,
        "total": 4,
        "percent_ready": 50,
    }


PDF_WRAPPED = """NET101 Computer Networks
Course Contents
Module I (10 lectures hours):
Network models, OSI layers, TCP/IP model, Physical layer, Small-
scale networks, Switching and routing, Routing
algorithms, Distance vector.
Studio Work / Laboratory Experiments:
Students will configure routers in the lab.
"""


def test_pdf_paragraphs_wrapped_across_lines_are_rejoined():
    items = parse_syllabus(PDF_WRAPPED)
    assert {item["unit"] for item in items} == {"Module I"}
    assert [item["title"] for item in items] == [
        "Network models",
        "OSI layers",
        "TCP/IP model",
        "Physical layer",
        "Small-scale networks",
        "Switching and routing",
        "Routing algorithms",
        "Distance vector",
    ]


def test_acronyms_comparisons_and_passing_mentions():
    topics = [
        {"id": "clock", "title": "Router clock", "text": "Every router has a clock."},
        {"id": "versus", "title": "Switch (L2) vs Router (L3)", "text": "Layers differ."},
        {"id": "tables", "title": "Routing tables", "text": "Entries may be static."},
    ]
    assert match("AI Router", topics) == []  # "AI" is not in any title
    assert match("Comparison with router", topics) == ["versus"]
    assert match("Static", topics) == []  # mentioned in passing on a slide only


def test_a_fading_topic_is_due_rather_than_ready():
    assert item_status(["ready", "review_due"]) == "review_due"
    assert item_status(["review_due", "not_started"]) == "practising"
    assert summarise(["ready", "review_due"])["percent_ready"] == 50
