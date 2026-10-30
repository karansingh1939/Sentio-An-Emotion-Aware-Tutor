"""The syllabus matching scores are computed correctly."""

import importlib.util
from pathlib import Path

script = Path(__file__).resolve().parents[2] / "scripts/eval/syllabus_matching.py"
spec = importlib.util.spec_from_file_location("syllabus_matching", script)
evaluation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evaluation)


def test_links_and_coverage_are_scored_separately():
    predicted = {0: ["a", "b"], 1: [], 2: ["c"]}
    labels = {0: ["a"], 1: ["d"], 2: []}
    measured = evaluation.scores(predicted, labels)
    assert measured["links"]["precision"] == 0.333  # 1 of 3 links made was right.
    assert measured["links"]["recall"] == 0.5  # 1 of 2 wanted links was found.
    assert measured["in_notes"]["precision"] == 0.5  # Item 2 is claimed but is a gap.
    assert measured["in_notes"]["recall"] == 0.5  # Item 1 is covered but was missed.


def test_embedding_ideas_change_word_matches_as_described():
    baseline = {0: ["a", "b"], 1: []}
    similar = {0: {"a": 0.9, "b": 0.5, "c": 0.8}, 1: {"a": 0.7, "b": 0.2, "c": 0.1}}
    assert evaluation.with_embeddings(baseline, similar, prune=0.1) == {0: ["a"], 1: []}
    assert evaluation.with_embeddings(baseline, similar, fill=0.6) == {0: ["a", "b"], 1: ["a"]}
    assert evaluation.with_embeddings(baseline, similar, fill=0.8)[1] == []
    assert evaluation.with_embeddings(baseline, similar, add=0.75)[0] == ["a", "b", "c"]


def test_nested_score_never_uses_held_out_labels_to_choose():
    baseline = {position: ["right"] for position in range(10)}
    worse = {position: ["wrong"] for position in range(10)}
    labels = {position: ["right"] for position in range(10)}
    assert evaluation.nested_score(baseline, labels, [worse])["links"]["f1"] == 1.0
