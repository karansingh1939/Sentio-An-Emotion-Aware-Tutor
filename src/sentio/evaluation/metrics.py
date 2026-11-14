import math
from statistics import mean


def retrieval_metrics(ranked, relevant, k=5):
    ranked = list(dict.fromkeys(ranked))[:k]
    relevant = set(relevant)
    if not relevant:
        return {
            "hit_at_5": None,
            "recall_at_5": None,
            "mrr": None,
            "returned_candidates": len(ranked),
        }
    hits = relevant.intersection(ranked)
    rank = next((i + 1 for i, item in enumerate(ranked) if item in relevant), None)
    return {
        "hit_at_5": float(bool(hits)),
        "recall_at_5": len(hits) / len(relevant),
        "mrr": 1 / rank if rank else 0,
        "returned_candidates": len(ranked),
    }


def aggregate(rows):
    result = {}
    for key in ("hit_at_5", "recall_at_5", "mrr", "latency_ms", "citation_support_hit"):
        values = [row[key] for row in rows if row.get(key) is not None]
        result[key] = mean(values) if values else None
    negatives = [r for r in rows if r["hit_at_5"] is None]
    result["irrelevant_candidate_rate"] = (
        mean(bool(r["returned_candidates"]) for r in negatives) if negatives else None
    )
    return result


def ndcg(ranked, relevant, k=10):
    """Binary-relevance nDCG@k."""
    gain = sum(
        1 / math.log2(rank + 1) for rank, item in enumerate(ranked[:k], 1) if item in relevant
    )
    ideal = sum(1 / math.log2(rank + 1) for rank in range(1, min(len(relevant), k) + 1))
    return gain / ideal if ideal else 0.0


def bootstrap_interval(values, resamples=2000, seed=0):
    """95% percentile bootstrap interval of the mean."""
    import numpy as np

    data = np.asarray(values, dtype=float)
    draws = np.random.default_rng(seed).integers(0, data.size, size=(resamples, data.size))
    means = data[draws].mean(axis=1)
    return [float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))]


def paired_bootstrap_p(first, second, resamples=2000, seed=0):
    """Two-sided paired bootstrap p-value for a difference in means over the same queries."""
    import numpy as np

    difference = np.asarray(first, dtype=float) - np.asarray(second, dtype=float)
    centred = difference - difference.mean()
    draws = np.random.default_rng(seed).integers(
        0, difference.size, size=(resamples, difference.size)
    )
    means = centred[draws].mean(axis=1)
    return float(np.mean(np.abs(means) >= abs(difference.mean())))
