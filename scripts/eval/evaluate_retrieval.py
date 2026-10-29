"""Run measured retrieval and optional local semantic grading evaluations."""

import argparse
import json
from pathlib import Path

from sentio.evaluation.runner import evaluate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=Path("tests/fixtures/evaluation_v1"))
    parser.add_argument("--output", type=Path, default=Path("reports/evaluation.json"))
    parser.add_argument("--grade", action="store_true", help="Run real Ollama semantic grading")
    args = parser.parse_args()
    result = evaluate(args.dataset, grade=args.grade)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {mode: value["summary"] for mode, value in result["retrieval"].items()}, indent=2
        )
    )
    print(f"Saved measurements to {args.output}")


if __name__ == "__main__":
    main()
