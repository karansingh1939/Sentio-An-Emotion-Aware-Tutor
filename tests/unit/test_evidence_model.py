from types import SimpleNamespace

import numpy as np
import pytest

from sentio.evaluation.evidence_corpus import build_corpus
from sentio.evaluation.evidence_dataset import pair_hash
from sentio.evaluation.evidence_features import collect_features
from sentio.evaluation.evidence_model import fit_development, gate_metrics, run_experiment


def test_annotation_preview_contains_all_pairs_and_refuses_training(tmp_path):
    corpus = build_corpus()
    pack = collect_features(corpus)
    assert len(pack["pairs"]) == 1584
    assert pack["mode"] == "keyword_only_annotation_preview"
    assert all(p["review_status"] == "pending_human_review" for p in pack["pairs"])
    with pytest.raises(ValueError, match="Manual review"):
        run_experiment(corpus, pack, [], tmp_path / "must-not-exist")
    assert not (tmp_path / "must-not-exist").exists()


def test_gate_counts_accepted_questions_without_support():
    rows = [
        {"question_id": "positive", "document_id": "relevant", "topic": "t", "label": 1},
        {"question_id": "positive", "document_id": "irrelevant", "topic": "t", "label": 0},
        {"question_id": "absent", "document_id": "other", "topic": "t", "label": 0},
    ]
    metrics, outcomes = gate_metrics(rows, [0.6, 0.9, 0.8], 0.7)
    assert metrics["coverage"] == 1
    assert metrics["answerable_coverage"] == 0
    assert metrics["unsupported_acceptance"] == 1
    assert metrics["accepted_without_support"] == 2
    assert metrics["recall_at_5"] == 1
    assert metrics["mrr"] == 0.5
    assert metrics["ndcg_at_5"] == pytest.approx(1 / np.log2(3))
    assert len(outcomes) == 2


def test_fit_uses_development_only_and_standardizes_train_features():
    rng = np.random.default_rng(42)

    def rows(name, shift):
        return [
            {
                "question_id": f"{name}-{i}",
                "document_id": str(i),
                "topic": name,
                "label": i % 2,
                "features": [i % 2 + shift, float(rng.normal()), 0, 2, 50, 1, 0],
            }
            for i in range(40)
        ]

    training, calibration, selection = (
        rows("train", 0),
        rows("calibration", 0.05),
        rows("selection", 0.1),
    )
    config, model, base, _ = fit_development(training, calibration, selection, [0, 1])
    np.testing.assert_allclose(
        base[0].mean_, np.mean([r["features"][:2] for r in training], axis=0)
    )
    assert 0.01 <= config["C"] <= 10
    assert model.predict_proba([[1, 0]])[0, 1] > model.predict_proba([[0, 0]])[0, 1]


def test_cpu_features_reuse_hybrid_ranking_without_label_features():
    corpus = build_corpus()
    encoder = SimpleNamespace(
        model_name="synthetic-fixture",
        encode=lambda texts, **kw: np.asarray([[len(text) / 1000, 1] for text in texts]),
    )
    pack = collect_features(corpus, encoder)
    first = pack["pairs"][0]
    assert len(first["features"]) == 7
    assert all(np.isfinite(first["features"]))
    question = corpus["questions"][0]
    document = corpus["documents"][0]
    assert first["pair_hash"] == pair_hash(question, document)
    assert first["features"][5] >= 1
    assert first["features"][6] >= 0


def test_synthetic_complete_run_exports_metrics_without_enabling_product_model(tmp_path):
    corpus = build_corpus()
    encoder = SimpleNamespace(
        model_name="synthetic-fixture",
        encode=lambda texts, **kw: np.asarray([[len(text) / 1000, 1] for text in texts]),
    )
    pack = collect_features(corpus, encoder)
    # Fixture-only labels exercise the full implementation, never populate the real dataset.
    annotations = [
        {
            "pair_id": pair["pair_id"],
            "pair_hash": pair["pair_hash"],
            "label": pair["proposed_label"],
            "review_status": "human_reviewed",
            "reviewer": "synthetic unit fixture",
            "rationale": "Synthetic regression label; no human review occurred.",
        }
        for pair in pack["pairs"]
    ]
    result = run_experiment(corpus, pack, annotations, tmp_path / "synthetic", render_plots=False)
    assert result["adoption"]["eligible"] is False
    assert len(result["ablations"]) == 7
    assert result["comparisons"]["cross_encoder"]["status"] == "unavailable"
    assert (tmp_path / "synthetic/model.joblib").is_file()
    assert (tmp_path / "synthetic/comparison.md").is_file()
    with pytest.raises(ValueError, match="immutable"):
        run_experiment(corpus, pack, annotations, tmp_path / "synthetic", render_plots=False)
