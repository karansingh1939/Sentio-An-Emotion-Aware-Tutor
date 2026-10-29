import json
from unittest.mock import Mock

from sentio.evaluation.generation_compare import measure


def test_saved_comparison_prompt_hashes_are_reproducible():
    from pathlib import Path

    from sentio.evaluation.evidence_dataset import digest
    from sentio.evaluation.generation_compare import comparison_messages

    root = Path(__file__).resolve().parents[2]
    profile = {"compact": False, "history_turns": 0, "max_tokens": 256}
    for filename, policy in (
        ("compare-cpu-v1.json", "legacy"),
        ("compare-grounding-v2.json", "grounding"),
    ):
        report = json.loads((root / "reports/generation" / filename).read_text())
        expected = {
            case["id"]: digest(
                comparison_messages(
                    case,
                    (root / "tests/fixtures/evaluation_v1" / case["expected_document"]).read_text(),
                    profile,
                    policy,
                )
            )
            for case in report["cases"]
        }
        assert all(
            row["messages_hash"] == expected[row["case_id"]]
            for model in report["models"].values()
            for row in model["runs"]
            if row["status"] == "measured"
        )


def response(chunks):
    result = Mock()
    result.__enter__ = lambda self: self
    result.__exit__ = lambda *args: False
    result.iter_lines.return_value = [json.dumps(chunk).encode() for chunk in chunks]
    return result


def test_stream_measure_requires_completion_and_uses_cpu_schema():
    case = {
        "id": "fixture",
        "kind": "answerable",
        "support": "net force",
        "expected_document": "forces.txt",
    }
    client = Mock()
    client.post.return_value = response(
        [
            {"message": {"content": '{"text":"A net force [forces.txt Page 1]"}'}},
            {"done": True, "done_reason": "stop"},
        ]
    )
    result = measure(client, "installed", case, [], "warm", 1)
    assert result["schema_valid"] and result["lexical_rubric_pass"]
    assert result["first_visible_seconds"] is not None
    payload = client.post.call_args.kwargs["json"]
    assert payload["options"]["num_gpu"] == 0
    assert payload["format"]["properties"]["text"]["type"] == "string"
    client.post.return_value = response(
        [{"message": {"content": '{"text":"A net force [forces.txt Page 1]"}'}}]
    )
    assert not measure(client, "installed", case, [], "cold", 1)["schema_valid"]
