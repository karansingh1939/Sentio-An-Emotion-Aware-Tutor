from unittest.mock import Mock

import pytest

from sentio.evaluation.runner import measure_grading


def test_blank_grading_is_reported_separately_from_semantic_inference(monkeypatch):
    backend = Mock()
    backend._session.get.return_value.json.return_value = {"models": []}
    monkeypatch.setattr("sentio.ai.providers.OllamaBackend", lambda: backend)
    cases = [
        dict(
            id="blank",
            question="Q",
            reference="A",
            answer=" ",
            expected_correct=False,
            score_range=[0, 0.59],
        ),
        dict(
            id="exact",
            question="Q",
            reference="A",
            answer="a",
            expected_correct=True,
            score_range=[0.6, 1],
        ),
    ]
    rows = measure_grading({"grading": cases})["cases"]
    assert [row["category"] for row in rows] == ["blank", "exact"]
    backend.complete.assert_not_called()


def test_ocr_error_rates_count_substitutions_deletions_and_insertions():
    from sentio.evaluation.ocr import error_rates

    assert error_rates("One two three", "one four three five")["word_error_rate"] == pytest.approx(
        2 / 3
    )
    assert error_rates("cat", "cut")["character_error_rate"] == pytest.approx(1 / 3)
    assert error_rates("One, TWO!", "one two")["word_error_rate"] == 0
    assert error_rates("one two", "")["word_error_rate"] == 1
    with pytest.raises(ValueError, match="reference"):
        error_rates("", "unexpected")


def test_numeric_grading_is_not_counted_as_model_inference(monkeypatch):
    backend = Mock()
    backend._session.get.return_value.json.return_value = {"models": []}
    monkeypatch.setattr("sentio.ai.providers.OllamaBackend", lambda: backend)
    rows = measure_grading(
        {
            "grading": [
                {
                    "id": "numeric",
                    "question": "One quarter as a percentage?",
                    "reference": "25 percent",
                    "answer": "0.25%",
                    "expected_correct": False,
                    "score_range": [0, 0.59],
                }
            ]
        }
    )["cases"]
    assert rows[0]["category"] == "numeric"
    assert rows[0]["rubric_pass"]
    backend.complete.assert_not_called()


@pytest.mark.parametrize("recognized", ["correct", "wrong"])
def test_ocr_evaluation_keeps_page_provenance_and_measures_engine_errors(monkeypatch, recognized):
    pytest.importorskip("pypdfium2")
    from sentio.evaluation import ocr as evaluation

    monkeypatch.setattr(evaluation.ocr, "require_ocr", lambda **kwargs: "fake-engine")
    monkeypatch.setattr(
        evaluation.subprocess, "run", lambda *args, **kwargs: Mock(stdout="test-engine\n")
    )

    def read(image):
        if image.convert("L").getextrema() == (255, 255):
            raise evaluation.ocr.ExtractionError("No readable English text found.")
        return evaluation.TEXT if recognized == "correct" else "Deliberately wrong recognition"

    monkeypatch.setattr(evaluation.ocr, "read_image", read)
    result = evaluation.evaluate()
    assert result["summary"]["structure_passed"] == 9
    assert result["summary"]["ocr_pages_measured"] == 8
    assert (result["summary"]["mean_word_error_rate"] == 0) == (recognized == "correct")
    mixed = next(case for case in result["cases"] if case["id"] == "mixed_pdf")
    assert [(page["page_number"], page["extraction_method"]) for page in mixed["pages"]] == [
        (1, "text"),
        (2, "ocr"),
    ]
    assert mixed["pages"][0]["text"] == evaluation.NATIVE_TEXT
