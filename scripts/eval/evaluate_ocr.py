"""Measure real local OCR against reproducibly generated English scan labels."""

import argparse
import json
from pathlib import Path

from sentio.evaluation.ocr import evaluate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--font", type=Path)
    parser.add_argument("--output", type=Path, default=Path("reports/ocr-evaluation.json"))
    args = parser.parse_args()
    result = evaluate(args.font)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print("OCR_EVALUATION_JSON=" + json.dumps(result), flush=True)
    return 0 if result["summary"]["structure_passed"] == result["summary"]["total_cases"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
