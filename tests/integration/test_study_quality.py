import pytest

from sentio.evaluation.study_quality import observe_answer


def test_recovery_is_not_counted_as_generated_answer_quality():
    case = {"kind": "answerable", "required_terms": ["inertia"], "forbidden_terms": []}
    row = observe_answer(
        case, {"text": "Inertia [notes.txt Page 1]", "answer_mode": "source_excerpt"}
    )
    assert row["outcome"] == "source_recovery"
    assert row["lexical_rubric_pass"] is False
    assert row["human_support_review"] is None


def test_missing_evidence_phrase_does_not_hide_a_forbidden_answer():
    case = {"kind": "absent", "required_terms": [], "forbidden_terms": ["78.37"]}
    row = observe_answer(
        case,
        {
            "text": "These notes do not contain that fact, but it is 78.37 C.",
            "answer_mode": "ollama",
        },
    )
    assert row["lexical_rubric_pass"] is False
    assert row["forbidden_terms_found"] == ["78.37"]


def test_supported_answer_with_later_limitation_is_not_an_abstention():
    row = observe_answer(
        {"kind": "answerable", "required_terms": ["less light"], "forbidden_terms": []},
        {
            "text": "A smaller aperture admits less light. The notes do not provide a diameter.",
            "answer_mode": "ollama",
            "source_citations": [{"filename": "notes.txt"}],
        },
    )
    assert row["outcome"] == "generated"
    assert row["lexical_rubric_pass"]


@pytest.mark.parametrize("kind", ["absent", "ambiguous"])
def test_abstention_and_clarification_have_separate_outcomes(kind):
    text = (
        "These notes do not contain enough information."
        if kind == "absent"
        else "Could you clarify which sample?"
    )
    row = observe_answer(
        {"kind": kind, "required_terms": [], "forbidden_terms": []},
        {"text": text, "answer_mode": "ollama"},
    )
    assert row["lexical_rubric_pass"]
    assert row["outcome"] in {"abstention", "clarification"}


def test_case_evaluator_uses_real_owned_api_context(tmp_path, monkeypatch):
    import json

    from fastapi.testclient import TestClient

    from sentio.api.app import agent, app
    from sentio.evaluation.study_quality import evaluate_cases
    from tests.helpers import login_student

    dataset = tmp_path / "cases.json"
    dataset.write_text(
        json.dumps(
            {
                "provenance": "Synthetic test fixture, not model quality evidence.",
                "documents": {
                    "fixture.txt": "Cedar retains eight grams of water. Its dry mass is forty grams."
                },
                "cases": [
                    {
                        "id": "fixture",
                        "document": "fixture.txt",
                        "topic": "Cedar",
                        "kind": "answerable",
                        "question": "How much water does Cedar retain?",
                        "required_terms": ["eight"],
                        "forbidden_terms": [],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    with TestClient(app) as client:
        owner = login_student(client)

        def complete(system_prompt, history, user_message, **kwargs):
            assert "eight grams" not in system_prompt
            assert "eight grams" in user_message
            return json.dumps({"text": "Cedar retains eight grams [fixture.txt Page 1]."}), 12

        monkeypatch.setattr(agent.nlp._backend, "complete", complete)

        def call(method, path, **kwargs):
            result = client.request(method, "/api/v1" + path, **kwargs)
            result.raise_for_status()
            return result.json()

        report = evaluate_cases(dataset, call, client, "/api/v1", owner)
    assert report["cases"][0]["outcome"] == "generated"
    assert report["summary"]["lexical_rubrics_passed"] == 1
    assert report["summary"]["semantic_accuracy"] is None


def test_required_and_forbidden_terms_match_whole_terms_only():
    case = {"kind": "answerable", "required_terms": ["8", "grams"], "forbidden_terms": ["0%"]}
    cited = {"answer_mode": "ollama/test", "source_citations": [{"filename": "a.txt", "page": 1}]}
    wrong = observe_answer(case, {**cited, "text": "Cedar retains 48 grams, 100% of it."})
    right = observe_answer(case, {**cited, "text": "Cedar retains 8 grams."})
    assert not wrong["lexical_rubric_pass"]
    assert wrong["forbidden_terms_found"] == []
    assert right["lexical_rubric_pass"]
