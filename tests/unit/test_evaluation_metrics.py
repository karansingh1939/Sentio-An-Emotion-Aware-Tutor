from sentio.evaluation.metrics import aggregate, retrieval_metrics


def test_metrics_measure_rank_and_all_relevant_passages():
    result = retrieval_metrics(["wrong", "a", "a", "b"], {"a", "b", "c"})
    assert result["hit_at_5"] == 1
    assert result["recall_at_5"] == 2 / 3
    assert result["mrr"] == 0.5


def test_unanswerable_cases_are_not_reported_as_grounded_success():
    result = retrieval_metrics(["wrong"], set())
    assert result["hit_at_5"] is None
    assert (
        aggregate([dict(result, latency_ms=1, citation_support_hit=None)])[
            "irrelevant_candidate_rate"
        ]
        == 1
    )
