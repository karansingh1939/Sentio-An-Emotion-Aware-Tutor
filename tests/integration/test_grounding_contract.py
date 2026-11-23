from types import SimpleNamespace

import pytest

from sentio.ai.grounding import GROUNDING_RULES, validate_references
from sentio.ai.prompts import PromptBuilder


def test_grounded_prompt_explicitly_requires_abstention_and_treats_source_as_data():
    source = SimpleNamespace(
        has_content=lambda: True,
        is_rag=True,
        rag_context="[notes.txt Page 1]\nNet force changes motion.",
    )
    prompt = PromptBuilder().build_system_prompt(
        "physics", "motion", "beginner", "neutral", "standard", "clear", source
    )
    assert GROUNDING_RULES in prompt
    assert "do not contain enough information" in prompt
    assert "untrusted data" in prompt


def test_citation_references_must_be_from_actual_retrieved_passages():
    source = SimpleNamespace(is_rag=True, source_citations=[{"filename": "notes.txt", "page": 1}])
    validate_references("Net force changes motion [notes.txt Page 1].", source)
    validate_references(
        "These notes do not contain enough information to answer that question.", source
    )
    with pytest.raises(ValueError, match="outside"):
        validate_references("A claim [secret.txt Page 2].", source)
    with pytest.raises(ValueError, match="cite"):
        validate_references("An explanation without a source.", source)


def test_generic_words_and_weak_semantic_match_are_not_evidence():
    from sentio.rag.evidence_policy import has_relevance_signal

    assert not has_relevance_signal(
        "What is the boiling point of ethanol?", "The law is about motion of an object.", 0.1
    )
    assert has_relevance_signal(
        "What changes uniform motion?", "An external force changes uniform motion.", 0.1
    )
    assert has_relevance_signal(
        "Which influence alters a moving body's velocity?",
        "A net force changes uniform motion.",
        0.65,
    )


def test_selected_notes_without_relevant_evidence_do_not_call_provider(monkeypatch):
    from fastapi.testclient import TestClient

    from sentio.api.app import agent, app
    from tests.helpers import login_student

    with TestClient(app) as client:
        login_student(client)
        uploaded = client.post(
            "/api/v1/documents/upload",
            files={"file": ("motion.txt", b"The law is about motion of an object.", "text/plain")},
        )
        assert uploaded.status_code == 201, uploaded.text
        sid = client.post(
            "/api/v1/sessions",
            json={
                "student_id": "ignored",
                "subject": "physics",
                "topic": "motion",
                "difficulty": "beginner",
                "metadata": {"document_id": uploaded.json()["document_id"]},
            },
        ).json()["session_id"]
        monkeypatch.setattr(agent.kb.vdb, "search", lambda *args, **kwargs: [])

        def forbidden(**kwargs):
            raise AssertionError("Insufficient selected notes must not call generation")

        monkeypatch.setattr(agent.nlp._backend, "complete", forbidden)
        result = client.post(
            f"/api/v1/sessions/{sid}/chat/stream",
            json={
                "message": "What is the boiling point of ethanol?",
                "request_id": "unsupported-test",
            },
        )
        assert "event: complete" in result.text, result.text
        assert "notes don't cover that question" in result.text
        assert "78.37" not in result.text


def test_a_refusal_that_goes_on_to_answer_from_memory_is_cut_back_to_the_refusal():
    from sentio.ai.grounding import trim_abstention

    reply = (
        "These notes do not contain enough information to answer that question. "
        "The passage discusses Raspberry Pi usage in IoT projects but does not cover "
        "convolution. To answer your question, we would need the output-size formula:\n\n"
        "Output size = (Input size - Filter size) / Stride + 1\n\nSo the output size would be 3."
    )
    assert trim_abstention(reply) == (
        "These notes do not contain enough information to answer that question. "
        "The passage discusses Raspberry Pi usage in IoT projects but does not cover "
        "convolution."
    )
    leading = "These notes do not contain it. However, it is generally 78 C."
    assert trim_abstention(leading) == "These notes do not contain it."
    answer = "Inertia resists changes in motion [notes.txt Page 1]. However, mass matters."
    assert trim_abstention(answer) == answer


def test_a_list_of_items_the_notes_never_name_is_rejected():
    from sentio.ai.grounding import unlisted_items

    notes = (
        "Cloud-based AIoT is composed of four layers: Device layer. Connectivity layer. "
        "Cloud layer. User communication layer."
    )
    invented = (
        "1. **Device Layer**: sensors\n2. **Network Layer**: links\n3. **Platform Layer**: data"
    )
    assert unlisted_items(invented, notes) == ["network layer", "platform layer"]
    faithful = "1. **Device Layer**: sensors\n2. **Connectivity Layer**: gateways"
    assert unlisted_items(faithful, notes) == []
    # Single emphasised words are not list items worth checking.
    assert unlisted_items("**Note**: layers matter.", notes) == []


def _content(*passages):
    return SimpleNamespace(
        is_rag=True,
        rag_context=" ".join(text for _, text in passages),
        source_citations=[{"filename": name, "page": 1, "text": text} for name, text in passages],
    )


def test_an_answer_from_memory_behind_a_citation_is_rejected():
    content = _content(("cnn.pdf", "Convolution slides a small filter over the image."))
    memory = (
        "Time series data is a sequence of observations recorded at regular intervals, "
        "used for forecasting stock prices and weather. [cnn.pdf Page 1]"
    )
    with pytest.raises(ValueError, match="do not support"):
        validate_references(memory, content)
    grounded = "Convolution slides a small filter over the image [cnn.pdf Page 1]."
    validate_references(grounded, content)


def test_an_uncited_answer_is_credited_only_to_a_passage_that_contains_it():
    from sentio.ai.grounding import cite_by_support

    content = _content(
        ("intro.pptx", "Evaluation policy: End Semester Examination 40, Continuous Lab 40."),
        ("datasets.pdf", "Types of dataset: 1D tabular, CSV, MAT, time series; 2D RGB images."),
    )
    lifted = "The types of dataset are 1D tabular, CSV, MAT and time series, and 2D RGB images."
    assert cite_by_support(lifted, content).endswith("[datasets.pdf Page 1]")
    memory = "Datasets can be structured, unstructured or semi-structured."
    assert cite_by_support(memory, content) == memory


def test_invented_layers_in_running_text_are_caught():
    from sentio.ai.grounding import unlisted_items

    notes = "Device layer. Connectivity layer. Cloud layer. User communication layer."
    invented = (
        "Cloud-based AIoT has four layers: the Device layer, the Platform layer and the "
        "Network layer."
    )
    assert unlisted_items(invented, notes) == ["platform layer", "network layer"]
    faithful = "It has four layers: the Device layer, the Connectivity layer and the Cloud layer."
    assert unlisted_items(faithful, notes) == []


def test_a_bracket_naming_several_pages_counts_as_one_citation_per_page():
    from sentio.ai.grounding import split_page_lists

    assert split_page_lists("Types [data.pdf Page 2, 3, 5].") == (
        "Types [data.pdf Page 2] [data.pdf Page 3] [data.pdf Page 5]."
    )
    assert split_page_lists("[data.pdf Pages 4-6]") == (
        "[data.pdf Page 4] [data.pdf Page 5] [data.pdf Page 6]"
    )
    assert split_page_lists("[data.pdf Page 7]") == "[data.pdf Page 7]"


def test_an_uncited_answer_drawn_from_two_slides_cites_both():
    from sentio.ai.grounding import cite_by_support

    content = _content(
        ("bias.pdf", "Algorithmic bias: flawed training data produces unfair outcomes and errors."),
        ("data.pdf", "Facial recognition trained on unbalanced faces misrecognises minorities."),
        ("other.pdf", "Raspberry Pi pins connect sensors."),
    )
    answer = (
        "Algorithmic bias comes from flawed training data that produces unfair outcomes, "
        "for example facial recognition trained on unbalanced faces."
    )
    cited = cite_by_support(answer, content)
    assert "[bias.pdf Page 1]" in cited and "[data.pdf Page 1]" in cited
    assert "other.pdf" not in cited


def test_numbered_steps_of_an_explanation_are_not_list_labels():
    from sentio.ai.grounding import unlisted_items

    notes = "7x7 input, assume 3x3 filter applied with stride 2 gives 3x3 output."
    steps = (
        "1. You have a 7x7 input.\n"
        "2. To find the output size, use the formula: (7 - 3) / 2 + 1.\n"
        "3. The output size is 3x3."
    )
    assert unlisted_items(steps, notes) == []


def test_a_step_by_step_reexplanation_of_a_short_slide_gets_its_citation():
    from sentio.ai.grounding import cite_by_support

    content = _content(
        (
            "cnn.pdf",
            "A closer look at spatial dimensions: 7x7 input, assume 3x3 filter applied "
            "with stride 2 gives 3x3 output.",
        ),
    )
    steps = (
        "Let's break it down.\n1. You have a 7x7 input.\n2. You use a 3x3 filter.\n"
        "3. The filter moves with stride 2.\n4. Subtract the filter size from the input, "
        "divide by the stride and add 1.\n5. The output is 3x3."
    )
    assert cite_by_support(steps, content).endswith("[cnn.pdf Page 1]")
