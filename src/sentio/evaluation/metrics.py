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
