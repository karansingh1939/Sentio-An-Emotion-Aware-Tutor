from sentio.evaluation.latency import PROFILES, messages_for, quality_check

CASE = {"query": "What changes motion?", "expected_document": "forces.txt", "support": "net force"}


def test_repeated_requests_have_identical_fresh_history_and_grounding():
    first = messages_for(CASE, "A net force changes motion.", PROFILES["baseline"])
    second = messages_for(CASE, "A net force changes motion.", PROFILES["baseline"])
    assert first == second
    first[1]["content"] = "Previous output must never leak into another run"
    assert first != second
    assert "forces.txt Page 1" in second[0]["content"]
    assert second[-1]["content"] == CASE["query"]


def test_each_experiment_changes_only_one_control():
    baseline = PROFILES["baseline"]
    for name, profile in PROFILES.items():
        if name != "baseline":
            assert sum(profile[key] != baseline[key] for key in baseline) == 1


def test_quality_rubric_requires_valid_response_support_and_citation():
    assert quality_check('{"text":"A net force [forces.txt Page 1]"}', CASE)
    assert not quality_check('{"text":"A net force"}', CASE)
    assert not quality_check('{"text":"BANANA [forces.txt Page 1]"}', CASE)
    assert not quality_check("not JSON", CASE)
