"""Reviewed-data logistic experiments. Imported only by the offline CLI."""

import json
import math
import platform
import time
from pathlib import Path

import numpy as np

from sentio.evaluation.evidence_dataset import digest, reviewed_labels
from sentio.evaluation.evidence_features import FEATURES


def gate_metrics(rows, scores, threshold, k=5):
    grouped = {}
    for row, score in zip(rows, scores, strict=True):
        grouped.setdefault(row["question_id"], []).append((row, score))
    outcomes, retrieval = [], []
    for question_id, candidates in grouped.items():
        relevant = sum(row["label"] for row, _ in candidates)
        candidates = sorted(
            (item for item in candidates if item[1] is not None),
            key=lambda item: (-item[1], item[0]["document_id"]),
        )[:k]
        accepted = bool(candidates and candidates[0][1] >= threshold)
        supported = bool(accepted and candidates[0][0]["label"])
        outcomes.append(
            {
                "question_id": question_id,
                "topic": candidates[0][0]["topic"]
                if candidates
                else grouped[question_id][0][0]["topic"],
                "answerable": bool(relevant),
                "accepted": accepted,
                "supported": supported,
            }
        )
        if relevant:
            hits = [row["label"] for row, _ in candidates]
            dcg = sum(label / math.log2(rank + 2) for rank, label in enumerate(hits))
            ideal = sum(1 / math.log2(rank + 2) for rank in range(min(k, relevant)))
            retrieval.append(
                {
                    "recall_at_5": sum(hits) / relevant,
                    "mrr": next((1 / (i + 1) for i, label in enumerate(hits) if label), 0),
                    "ndcg_at_5": dcg / ideal,
                }
            )
    answerable = [r for r in outcomes if r["answerable"]]
    unsupported = [r for r in outcomes if not r["answerable"]]
    accepted_count = sum(r["accepted"] for r in outcomes)
    supported_count = sum(r["supported"] for r in outcomes)
    precision = supported_count / accepted_count if accepted_count else 0
    recall = supported_count / len(answerable) if answerable else 0
    summary = {
        "coverage": accepted_count / len(outcomes) if outcomes else 0,
        "answerable_coverage": recall,
        "unsupported_acceptance": sum(r["accepted"] for r in unsupported) / len(unsupported)
        if unsupported
        else None,
        "rejected_answerable": sum(not r["accepted"] for r in answerable),
        "accepted_without_support": accepted_count - supported_count,
        "support_precision": precision,
        "support_recall": recall,
        "support_f1": 2 * precision * recall / (precision + recall) if precision + recall else 0,
        "question_count": len(outcomes),
        "answerable_count": len(answerable),
        "unsupported_count": len(unsupported),
    }
    for metric in ("recall_at_5", "mrr", "ndcg_at_5"):
        summary[metric] = float(np.mean([r[metric] for r in retrieval])) if retrieval else None
    return summary, outcomes


def choose_threshold(rows, scores):
    finite = [float(value) for value in scores if value is not None]
    choices = sorted(set(finite + [max(finite, default=0) + 1]))
    # Only development rows reach this function. A tie favours less unsupported acceptance.
    scored = [(gate_metrics(rows, scores, value)[0], value) for value in choices]
    return max(
        scored,
        key=lambda item: (
            item[0]["support_f1"],
            -(item[0]["unsupported_acceptance"] or 0),
            item[1],
        ),
    )[1]


def candidate_scores(rows, probabilities):
    return [
        float(value) if row["features"][5] <= 10 else None
        for row, value in zip(rows, probabilities, strict=True)
    ]


def bootstrap_outcomes(outcomes, repeats=1000):
    """Question-group resampling; with two test topics this is exploratory only."""
    rng = np.random.default_rng(42)
    metrics = {"coverage": [], "answerable_coverage": [], "unsupported_acceptance": []}
    for _ in range(repeats):
        sampled = [outcomes[i] for i in rng.integers(0, len(outcomes), len(outcomes))]
        positive = [r for r in sampled if r["answerable"]]
        negative = [r for r in sampled if not r["answerable"]]
        metrics["coverage"].append(np.mean([r["accepted"] for r in sampled]))
        if positive:
            metrics["answerable_coverage"].append(np.mean([r["supported"] for r in positive]))
        if negative:
            metrics["unsupported_acceptance"].append(np.mean([r["accepted"] for r in negative]))
    return {
        key: np.quantile(values, [0.025, 0.975]).tolist() if values else None
        for key, values in metrics.items()
    }


def fit_development(train, calibration, selection, columns):
    from sklearn.calibration import CalibratedClassifierCV
    from sklearn.frozen import FrozenEstimator
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import brier_score_loss
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    def xy(rows):
        return np.asarray([row["features"] for row in rows], dtype=float)[:, columns], np.asarray(
            [row["label"] for row in rows]
        )

    xt, yt = xy(train)
    xc, yc = xy(calibration)
    xs, ys = xy(selection)
    if any(len(set(values)) != 2 for values in (yt, yc, ys)):
        raise ValueError(
            "Train, calibration and selection groups each require both reviewed classes"
        )
    candidates = []
    for strength in (0.01, 0.1, 1, 10):
        base = make_pipeline(
            StandardScaler(),
            LogisticRegression(C=strength, class_weight="balanced", max_iter=2000, random_state=42),
        )
        base.fit(xt, yt)
        calibrated = CalibratedClassifierCV(FrozenEstimator(base), method="sigmoid")
        calibrated.fit(xc, yc)
        for name, model in (("uncalibrated", base), ("sigmoid", calibrated)):
            scores = model.predict_proba(xs)[:, 1]
            candidates.append((float(brier_score_loss(ys, scores)), strength, name, model, base))
    best = min(candidates, key=lambda row: (row[0], row[1], row[2]))
    scores = candidate_scores(selection, best[3].predict_proba(xs)[:, 1])
    return (
        {
            "selection_brier": best[0],
            "C": best[1],
            "calibration": best[2],
            "threshold": choose_threshold(selection, scores),
        },
        best[3],
        best[4],
        candidates,
    )


def run_experiment(corpus, pack, annotations, output, track=False, render_plots=True):
    from sklearn.calibration import calibration_curve
    from sklearn.metrics import brier_score_loss, precision_score, recall_score

    labels = reviewed_labels(corpus, pack["pairs"], annotations)  # Must precede any fitting.
    if pack["corpus_hash"] != digest(corpus) or pack["feature_names"] != FEATURES:
        raise ValueError("Feature schema or corpus hash mismatch")
    if pack["mode"] != "cached_cpu":
        raise ValueError("Keyword annotation previews are not a complete CPU model experiment")
    output = Path(output)
    if output.exists():
        raise ValueError("Runs are immutable; choose a new output directory")
    if render_plots:
        import matplotlib

        matplotlib.use("Agg")
    rows = [dict(pair, label=label) for pair, label in zip(pack["pairs"], labels, strict=True)]
    documents = {d["document_id"]: d for d in corpus["documents"]}
    for question in corpus["questions"]:
        actual = [r["document_id"] for r in rows if r["question_id"] == question["question_id"]]
        expected = {d["document_id"] for d in documents.values() if d["split"] == question["split"]}
        if len(actual) != len(set(actual)) or set(actual) != expected:
            raise ValueError("Every question needs reviewed coverage of its complete split corpus")
    matrix = np.asarray([r["features"] for r in rows], dtype=float)
    if matrix.shape != (len(rows), len(FEATURES)) or not np.isfinite(matrix).all():
        raise ValueError("Missing or non-finite evidence features")
    train = [r for r in rows if r["split"] == "train"]
    calibration_topic, selection_topic = corpus["splits"]["validation"]
    calibration = [r for r in rows if r["topic"] == calibration_topic]
    selection = [r for r in rows if r["topic"] == selection_topic]
    test = [r for r in rows if r["split"] == "test"]
    columns = list(range(len(FEATURES)))
    config, model, base, candidates = fit_development(train, calibration, selection, columns)
    baseline_selection_scores = [r["scores"]["hybrid"] for r in selection]
    baseline_threshold = choose_threshold(selection, baseline_selection_scores)
    baseline_selection = gate_metrics(selection, baseline_selection_scores, baseline_threshold)[0]
    selection_probabilities = candidate_scores(
        selection,
        model.predict_proba(np.asarray([r["features"] for r in selection], dtype=float))[:, 1],
    )
    eligible_thresholds = []
    for threshold in sorted({value for value in selection_probabilities if value is not None}):
        metrics = gate_metrics(selection, selection_probabilities, threshold)[0]
        if (
            metrics["answerable_coverage"] >= baseline_selection["answerable_coverage"]
            and metrics["unsupported_acceptance"] is not None
            and baseline_selection["unsupported_acceptance"] is not None
            and metrics["unsupported_acceptance"] < baseline_selection["unsupported_acceptance"]
        ):
            eligible_thresholds.append(
                (metrics["unsupported_acceptance"], -metrics["answerable_coverage"], threshold)
            )
    config["validation_quality_gate"] = bool(eligible_thresholds)
    if eligible_thresholds:
        config["threshold"] = min(eligible_thresholds)[2]
    result = {
        "corpus_hash": digest(corpus),
        "feature_packet_hash": digest(pack),
        "annotation_hash": digest(annotations),
        "feature_names": FEATURES,
        "config": config,
        "calibration_topic": calibration_topic,
        "selection_topic": selection_topic,
        "hardware": pack["hardware"],
        "versions": pack["versions"],
        "platform": platform.platform(),
        "probability_event": "passage contains sufficient evidence; not generated-answer correctness",
        "comparisons": {},
        "ablations": {},
        "limitations": [
            "Author-reviewed labels are not independent ground truth.",
            "Only two test topics and short source notes; no student-learning study.",
            "Split-specific corpora do not measure large-library search or production Qdrant latency.",
            "Intervals resample questions, not an adequately large population of topics.",
        ],
    }
    for name in ("keyword", "dense", "hybrid", "cross_encoder"):
        scores = [r["scores"][name] for r in test]
        development_scores = [r["scores"][name] for r in selection]
        if all(value is None for value in scores):
            result["comparisons"][name] = {"status": "unavailable"}
            continue
        threshold = choose_threshold(selection, development_scores)
        summary, outcomes = gate_metrics(test, scores, threshold)
        latency = [
            q["latency_ms"][name]
            for q in pack["queries"]
            if q["split"] == "test" and q["latency_ms"][name] is not None
        ]
        result["comparisons"][name] = {
            "status": "measured",
            "threshold": threshold,
            "metrics": summary,
            "question_intervals_95": bootstrap_outcomes(outcomes),
            "latency_p95_ms": float(np.quantile(latency, 0.95)) if latency else None,
        }
    xtest = np.asarray([r["features"] for r in test], dtype=float)
    tick = time.perf_counter()
    probabilities = model.predict_proba(xtest)[:, 1]
    prediction_ms = (time.perf_counter() - tick) * 1000
    summary, outcomes = gate_metrics(
        test, candidate_scores(test, probabilities), config["threshold"]
    )
    ytest = np.asarray([r["label"] for r in test])
    observed, predicted = calibration_curve(ytest, probabilities, n_bins=8)
    learned = {
        "status": "measured",
        "threshold": config["threshold"],
        "metrics": summary,
        "brier": float(brier_score_loss(ytest, probabilities)),
        "pair_precision": float(
            precision_score(ytest, probabilities >= config["threshold"], zero_division=0)
        ),
        "pair_recall": float(
            recall_score(ytest, probabilities >= config["threshold"], zero_division=0)
        ),
        "reliability": {"predicted": predicted.tolist(), "observed": observed.tolist()},
        "question_intervals_95": bootstrap_outcomes(outcomes),
        "batch_prediction_ms": prediction_ms,
    }
    result["comparisons"]["learned"] = learned
    question_kinds = {q["question_id"]: q["kind"] for q in corpus["questions"]}
    result["question_kind_slices"] = {}
    for kind in ("direct", "paraphrase", "ambiguous", "absent"):
        indices = [i for i, row in enumerate(test) if question_kinds[row["question_id"]] == kind]
        sliced_rows = [test[i] for i in indices]
        sliced_scores = [
            float(probabilities[i]) if test[i]["features"][5] <= 10 else None for i in indices
        ]
        result["question_kind_slices"][kind] = gate_metrics(
            sliced_rows, sliced_scores, config["threshold"]
        )[0]
    # Report both calibrated and uncalibrated candidates without selecting on test performance.
    result["regularization_selection"] = [
        {"C": row[1], "calibration": row[2], "selection_brier": row[0]} for row in candidates
    ]
    result["calibration_comparison"] = [
        {
            "C": row[1],
            "calibration": row[2],
            "selection_brier": row[0],
            "test_brier": float(brier_score_loss(ytest, row[3].predict_proba(xtest)[:, 1])),
        }
        for row in candidates
        if row[1] == config["C"]
    ]
    for removed, index in zip(FEATURES, columns, strict=True):
        remaining = [i for i in columns if i != index]
        ablation_config, ablation, _, _ = fit_development(train, calibration, selection, remaining)
        scores = ablation.predict_proba(xtest[:, remaining])[:, 1]
        result["ablations"][removed] = {
            "config": ablation_config,
            "metrics": gate_metrics(
                test, candidate_scores(test, scores), ablation_config["threshold"]
            )[0],
        }
    baseline = result["comparisons"]["hybrid"]
    improved = (
        config["validation_quality_gate"]
        and baseline["status"] == "measured"
        and summary["unsupported_acceptance"] is not None
        and summary["unsupported_acceptance"] < baseline["metrics"]["unsupported_acceptance"]
        and summary["answerable_coverage"] >= baseline["metrics"]["answerable_coverage"]
    )
    result["adoption"] = {
        "eligible": False,
        "offline_quality_gate": improved,
        "reason": "Production retrieval latency and grounded live-answer review remain required; baseline retained.",
    }
    result["failure_cases"] = [
        row
        for row in outcomes
        if (row["accepted"] and not row["supported"]) or (row["answerable"] and not row["accepted"])
    ]
    output.mkdir(parents=True)
    if render_plots:
        import matplotlib.pyplot as plt

        figure, axes = plt.subplots(1, 2, figsize=(9, 4), constrained_layout=True)
        axes[0].plot([0, 1], [0, 1], linestyle="--", color="gray", label="Ideal calibration")
        for candidate in candidates:
            if candidate[1] != config["C"]:
                continue
            values = candidate[3].predict_proba(xtest)[:, 1]
            frequency, mean_probability = calibration_curve(ytest, values, n_bins=8)
            axes[0].plot(mean_probability, frequency, marker="o", label=candidate[2])
        axes[0].set(
            xlabel="Mean predicted passage support",
            ylabel="Observed sufficient evidence",
            title="Frozen test reliability",
        )
        axes[0].legend()
        axes[1].hist(probabilities, bins=np.linspace(0, 1, 9), edgecolor="white")
        axes[1].set(
            xlabel="Predicted passage support", ylabel="Pair count", title="Score distribution"
        )
        figure.savefig(output / "calibration.png", dpi=160)
        plt.close(figure)
    lines = [
        "# Evidence comparison",
        "",
        "Small author-reviewed corpus; no learning-effectiveness claim.",
        "",
        "| Method | Recall@5 | MRR | nDCG@5 | Answerable coverage | Unsupported acceptance |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for name, comparison in result["comparisons"].items():
        if comparison["status"] != "measured":
            lines.append(f"| {name} | unavailable | — | — | — | — |")
            continue
        metrics = comparison["metrics"]
        values = [
            f"{metrics[key]:.3f}" if metrics[key] is not None else "n/a"
            for key in (
                "recall_at_5",
                "mrr",
                "ndcg_at_5",
                "answerable_coverage",
                "unsupported_acceptance",
            )
        ]
        lines.append("| " + name + " | " + " | ".join(values) + " |")
    lines.extend(
        ["", "Adoption: baseline retained pending production latency and live-answer review.", ""]
    )
    (output / "comparison.md").write_text("\n".join(lines), encoding="utf-8")
    (output / "report.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    import joblib

    joblib.dump(
        model, output / "model.joblib"
    )  # Local trusted experiment only; never auto-loaded by the app.
    if track:
        import mlflow

        mlflow.set_tracking_uri((output.parent / "mlruns").absolute().as_uri())
        mlflow.set_experiment("Sentio passage evidence")
        with mlflow.start_run():
            mlflow.log_params(
                {
                    "corpus_hash": result["corpus_hash"],
                    "annotations": result["annotation_hash"],
                    "features": len(FEATURES),
                    "C": config["C"],
                    "calibration": config["calibration"],
                }
            )
            mlflow.log_metrics(
                {
                    "test_brier": learned["brier"],
                    "answerable_coverage": summary["answerable_coverage"],
                    "unsupported_acceptance": summary["unsupported_acceptance"] or 0,
                }
            )
            mlflow.log_artifact(str(output / "report.json"))
    return result
