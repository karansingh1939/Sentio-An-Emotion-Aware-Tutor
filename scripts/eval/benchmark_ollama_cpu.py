"""Measure equivalent, fresh-context local CPU prompts, cold and warm separately."""

import argparse
import json
from pathlib import Path

from sentio.evaluation.generation_compare import compare_models
from sentio.evaluation.latency import benchmark


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=Path("tests/fixtures/evaluation_v1"))
    parser.add_argument("--output", type=Path, default=Path("reports/latency.json"))
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--cases", type=int, default=3)
    parser.add_argument("--models", nargs="+", help="Installed tags for schema-stream comparison")
    parser.add_argument("--prompt-policy", choices=("legacy", "grounding"), default="grounding")
    args = parser.parse_args()
    result = (
        compare_models(args.dataset, args.models, args.output, args.repetitions, args.prompt_policy)
        if args.models
        else benchmark(args.dataset, args.repetitions, args.cases)
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"Saved CPU measurements to {args.output}")


if __name__ == "__main__":
    main()
