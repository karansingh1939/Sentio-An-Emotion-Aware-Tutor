"""PowerPoint lectures become one page per slide, with tables and speaker notes."""

from pptx import Presentation
from pptx.util import Inches

from sentio.ingestion.pipeline import DocumentIngestionPipeline


def _deck(path):
    deck = Presentation()
    first = deck.slides.add_slide(deck.slide_layouts[1])
    first.shapes.title.text = "Process scheduling"
    first.placeholders[1].text_frame.text = "Round robin gives each process a time slice."
    first.notes_slide.notes_text_frame.text = "Ask about starvation."
    deck.slides.add_slide(deck.slide_layouts[6])  # blank slide
    third = deck.slides.add_slide(deck.slide_layouts[5])
    third.shapes.title.text = "Comparison"
    table = third.shapes.add_table(2, 2, Inches(1), Inches(2), Inches(4), Inches(1)).table
    for row, values in enumerate([("Policy", "Preemptive"), ("FCFS", "No")]):
        for column, value in enumerate(values):
            table.cell(row, column).text = value
    deck.save(path)


def test_slides_become_numbered_pages(tmp_path):
    path = tmp_path / "lecture.pptx"
    _deck(path)
    pages = DocumentIngestionPipeline.parse_pptx(None, path)

    assert [page["page_number"] for page in pages] == [1, 3]
    assert pages[0]["text"].splitlines() == [
        "Process scheduling",
        "Round robin gives each process a time slice.",
        "Notes: Ask about starvation.",
    ]
    assert pages[1]["text"].splitlines() == ["Comparison", "Policy | Preemptive", "FCFS | No"]
