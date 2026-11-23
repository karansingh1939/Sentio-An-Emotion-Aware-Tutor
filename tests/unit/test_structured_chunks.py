"""Passages follow a page's structure, and repeated passages are shown once."""

from sentio.ingestion.pipeline import CHUNK_CHARS, DocumentIngestionPipeline
from sentio.rag.knowledge_base import distinct_passages

CLOUD_LAYERS = (
    "Cloud-based AIoT is composed of the following four layers: Device layer. This includes "
    "tags, beacons, sensors. Connectivity layer. This layer comprises field and cloud "
    "gateways. Cloud layer. This consists of data processing via an AI engine. User "
    "communication layer. This layer is made up of web portals and mobile applications."
)


def chunk(text):
    return DocumentIngestionPipeline.chunk_text(
        DocumentIngestionPipeline.__new__(DocumentIngestionPipeline), text
    )


def test_a_slide_that_fits_is_one_passage_so_its_list_stays_whole():
    # C4a: a fixed 500-character window cut this list after "Device layer".
    (only,) = chunk(CLOUD_LAYERS)
    for layer in ("Device", "Connectivity", "Cloud layer", "User communication"):
        assert layer in only


def test_a_long_page_splits_between_lines_without_overlap_or_broken_words():
    page = "\n".join(f"Bullet {i}: " + "concept " * 40 for i in range(12))
    passages = chunk(page)
    assert all(len(p) <= CHUNK_CHARS for p in passages)
    # Every line survives exactly once, in order (lines are stripped of edge spaces).
    assert [line for p in passages for line in p.split("\n")] == [
        line.strip() for line in page.split("\n")
    ]
    assert all(p.startswith("Bullet") for p in passages)


def test_an_over_long_line_splits_at_a_space():
    passages = chunk("token " * 400)
    assert all(len(p) <= CHUNK_CHARS and not p.startswith(" ") for p in passages)
    assert sum(p.count("token") for p in passages) == 400


def test_a_copy_of_a_lecture_does_not_fill_the_results_twice():
    # B14: an uploaded copy put every page into the top five twice.
    ranked = [
        {"id": 1, "text": "SUPPORT VECTOR MACHINES separator separable more than one"},
        {"id": 2, "text": "SUPPORT VECTOR MACHINES separator separable more than one"},
        {"id": 3, "text": "maximum margin hyperplane between the classes"},
        {"id": 4, "text": "maximum margin hyperplane between the classes"},
        {"id": 5, "text": "support vectors are the closest points"},
    ]
    assert [hit["id"] for hit in distinct_passages(ranked, kept=5)] == [1, 3, 5]
