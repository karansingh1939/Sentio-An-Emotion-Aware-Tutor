"""Compare the production grader with a candidate prompt using fresh requests."""

import argparse
import hashlib
import json
import platform
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import psutil

from sentio.ai.prompts import grading_prompt
from sentio.evaluation.runner import measure_grading

CLARIFICATION = (
    " Judge essential meaning, not matching words. Interpret the student's wording in the "
    "context of the question. A complete paraphrase earns 1.0 even if it omits nonessential "
    "reference wording. Reserve scores below 0.6 for missing essential concepts or factual errors. "
    "For example: question 'What does friction do?', reference 'Opposes relative motion', "
    "answer 'Resists sliding' earns 1.0; answer 'Speeds up sliding' earns 0.0. "
    "Equivalent fractions, decimals and percentages are correct; different magnitudes are not. "
    "Additional contradictory claims make an otherwise matching answer incorrect."
)


def candidate_prompt(question, reference):
    return grading_prompt(question, reference) + CLARIFICATION


def summarize(cases):
    semantic = [case for case in cases if case["category"] == "semantic"]
    return {
        "rubrics_passed": sum(case["rubric_pass"] for case in cases),
        "total": len(cases),
        "semantic_rubrics_passed": sum(case["rubric_pass"] for case in semantic),
        "semantic_total": len(semantic),
        "false_positives": sum(
            case.get("correct") is True and not case["expected_correct"] for case in semantic
        ),
        "false_negatives": sum(
            case.get("correct") is False and case["expected_correct"] for case in semantic
        ),
        "errors": sum("error" in case for case in cases),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=Path("tests/fixtures/grading_v2.json"))
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--output", type=Path, default=Path("reports/grading-comparison.json"))
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("--repeats must be positive")
    raw = args.dataset.read_bytes()
    dataset = json.loads(raw)
    result = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dataset_version": dataset["version"],
        "dataset_sha256": hashlib.sha256(raw).hexdigest(),
        "provenance": dataset["provenance"],
        "hardware": {
            "platform": platform.platform(),
            "cpu": platform.processor(),
            "logical_cpus": psutil.cpu_count(),
            "ram_bytes": psutil.virtual_memory().total,
        },
        "configuration": {
            "temperature": 0.0,
            "max_output_tokens": 512,
            "history": [],
            "repeats": args.repeats,
        },
        "prompts": {
            "baseline": grading_prompt("QUESTION", "REFERENCE"),
            "candidate": candidate_prompt("QUESTION", "REFERENCE"),
        },
        "runs": [],
    }
    for repeat in range(args.repeats):
        # Alternate order to reduce systematic cold/warm ordering bias.
        profiles = [("baseline", grading_prompt), ("candidate", candidate_prompt)]
        if repeat % 2:
            profiles.reverse()
        for name, prompt in profiles:
            with patch("sentio.quiz.service.grading_prompt", prompt):
                run = measure_grading(dataset)
            run.update(profile=name, repeat=repeat + 1, summary=summarize(run["cases"]))
            result["runs"].append(run)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
            print(json.dumps({"profile": name, "repeat": repeat + 1, **run["summary"]}), flush=True)


if __name__ == "__main__":
    main()
