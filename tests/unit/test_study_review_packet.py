import hashlib
import json

import pytest
from scripts.eval.prepare_study_review import prepare


def test_review_packet_binds_actual_answers_to_sources_and_has_no_proposed_labels(tmp_path):
    dataset = tmp_path / "dataset.json"
    dataset.write_text(
        json.dumps({"documents": {"notes.txt": "Cedar retains eight grams."}}), encoding="utf-8"
    )
    report = tmp_path / "report.json"
    report.write_text(
        json.dumps(
            {
                "grounding_evaluation": {
                    "dataset_sha256": hashlib.sha256(dataset.read_bytes()).hexdigest(),
                    "cases": [
                        {
                            "case_id": "c1",
                            "document": "notes.txt",
                            "question": "How much water?",
                            "lexical_rubric_pass": True,
                            "response": {"text": "<script>alert(1)</script> Eight grams."},
                        }
                    ],
                }
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "review.html"
    assert prepare(dataset, report, output) == 1
    html = output.read_text(encoding="utf-8")
    assert "Accept reply" in html and "Reject reply" in html
    assert "lexical_rubric_pass" not in html
    assert "<script>alert(1)</script>" not in html
    dataset.write_text('{"documents": {}}', encoding="utf-8")
    with pytest.raises(ValueError, match="do not match"):
        prepare(dataset, report, tmp_path / "different.html")
