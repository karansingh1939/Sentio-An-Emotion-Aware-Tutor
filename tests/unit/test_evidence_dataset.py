from copy import deepcopy

import pytest

from sentio.evaluation.evidence_corpus import build_corpus
from sentio.evaluation.evidence_dataset import (
    freeze_corpus,
    load_corpus,
    pair_hash,
    reviewed_labels,
    validate_corpus,
)


def test_corpus_is_frozen_and_question_variants_cannot_leak(tmp_path):
    corpus = build_corpus()
    assert len(corpus["documents"]) == 30
    assert len(corpus["questions"]) == 120
    manifest = freeze_corpus(corpus, tmp_path)
    assert load_corpus(tmp_path)[1] == manifest
    with pytest.raises(ValueError, match="overwritten"):
        freeze_corpus(corpus, tmp_path)
    broken = deepcopy(corpus)
    broken["questions"][0]["split"] = "test"
    with pytest.raises(ValueError, match="leakage"):
        validate_corpus(broken)
    (tmp_path / "corpus.json").write_text(
        (tmp_path / "corpus.json").read_text().replace("Dot products", "Changed title")
    )
    with pytest.raises(ValueError, match="changed"):
        load_corpus(tmp_path)


def test_training_labels_require_manual_review_bound_to_source_text():
    corpus = build_corpus()
    question, document = corpus["questions"][0], corpus["documents"][0]
    pair = {
        "pair_id": "test-fixture",
        "question_id": question["question_id"],
        "document_id": document["document_id"],
    }
    with pytest.raises(ValueError, match="Manual review"):
        reviewed_labels(corpus, [pair], [])
    # Synthetic annotation tests the contract; it is never a portfolio label.
    annotation = {
        "pair_id": pair["pair_id"],
        "review_status": "human_reviewed",
        "reviewer": "test fixture",
        "rationale": "Synthetic unit-test label only",
        "label": 1,
        "pair_hash": pair_hash(question, document),
    }
    assert reviewed_labels(corpus, [pair], [annotation]) == [1]
    changed = deepcopy(corpus)
    changed["documents"][0]["text"] += " Altered passage."
    with pytest.raises(ValueError, match="changed"):
        reviewed_labels(changed, [pair], [annotation])
