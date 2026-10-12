"""Create a new frozen, explicitly unreviewed original academic corpus."""

import argparse
from pathlib import Path

from sentio.evaluation.evidence_corpus import build_corpus
from sentio.evaluation.evidence_dataset import freeze_corpus


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("datasets/evidence_v1"))
    args = parser.parse_args()
    manifest = freeze_corpus(build_corpus(), args.output)
    print(f"Frozen 30 documents / 120 questions: {manifest['corpus_hash']}")
    print("Labels and academic drafts require human review; no training result is claimed.")


if __name__ == "__main__":
    main()
