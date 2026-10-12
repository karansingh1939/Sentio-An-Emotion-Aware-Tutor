"""Prepare auditable evidence annotations or train strictly reviewed local data."""

import argparse
import json
from pathlib import Path

from sentio.evaluation.evidence_dataset import digest, load_corpus, pair_hash
from sentio.evaluation.evidence_features import cached_models, collect_features


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=Path("datasets/evidence_v1"))
    sub = parser.add_subparsers(dest="command", required=True)
    prepare = sub.add_parser("prepare")
    prepare.add_argument("--output", type=Path, required=True)
    prepare.add_argument(
        "--keyword-only", action="store_true", help="Annotation preview; not trainable"
    )
    prepare.add_argument("--encoder", default="all-MiniLM-L6-v2")
    review = sub.add_parser("review")
    review.add_argument("--features", type=Path, required=True)
    review.add_argument("--annotations", type=Path, required=True)
    review.add_argument("--reviewer", required=True)
    review.add_argument("--split", choices=["train", "validation", "test"], required=True)
    export = sub.add_parser("review-page")
    export.add_argument("--features", type=Path, required=True)
    export.add_argument("--output", type=Path, required=True)
    train = sub.add_parser("train")
    train.add_argument("--features", type=Path, required=True)
    train.add_argument("--annotations", type=Path, required=True)
    train.add_argument("--output", type=Path, required=True)
    train.add_argument("--mlflow", action="store_true")
    args = parser.parse_args()
    corpus, manifest = load_corpus(args.dataset)
    if args.command == "prepare":
        if args.output.exists():
            parser.error("Feature packets are immutable; choose a new output path")
        encoder, reranker = (None, None) if args.keyword_only else cached_models(args.encoder)
        pack = collect_features(corpus, encoder, reranker)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(pack, indent=2) + "\n", encoding="utf-8")
        print(f"Prepared {len(pack['pairs'])} unreviewed pairs; corpus {manifest['corpus_hash']}")
        return
    pack = read_json(args.features)
    if pack["corpus_hash"] != manifest["corpus_hash"]:
        parser.error("Feature packet belongs to another frozen corpus")
    if args.command == "review-page":
        from sentio.evaluation.evidence_review import export_review

        count = export_review(corpus, pack, args.output)
        print(
            f"Open {args.output.resolve()} in your browser: {count} passages, no proposed labels shown."
        )
        return
    annotations = read_json(args.annotations) if args.annotations.exists() else []
    if args.command == "review":
        reviewed = {row["pair_id"] for row in annotations}
        questions = {q["question_id"]: q for q in corpus["questions"]}
        documents = {d["document_id"]: d for d in corpus["documents"]}
        print(
            "Rubric: 1 only if this passage alone supports a complete answer without outside facts."
        )
        print(
            "Ambiguous referents and absent evidence are 0. Read the passage; proposals are hidden."
        )
        for pair in pack["pairs"]:
            if pair["split"] != args.split or pair["pair_id"] in reviewed:
                continue
            question, document = questions[pair["question_id"]], documents[pair["document_id"]]
            print(f"\n{pair['pair_id']}\nQuestion: {question['text']}\nPassage: {document['text']}")
            label = input("Sufficient evidence? [1/0, s=skip, q=quit]: ").strip()
            if label == "q":
                break
            if label not in ("0", "1"):
                continue
            rationale = input(
                "Rationale (quote or identify supporting/missing information): "
            ).strip()
            if len(rationale) < 10 or not args.reviewer.strip():
                print("A named reviewer and rationale of at least ten characters are required.")
                continue
            annotations.append(
                {
                    "pair_id": pair["pair_id"],
                    "label": int(label),
                    "pair_hash": pair_hash(question, document),
                    "review_status": "human_reviewed",
                    "reviewer": args.reviewer.strip(),
                    "rationale": rationale,
                }
            )
            args.annotations.parent.mkdir(parents=True, exist_ok=True)
            staged = args.annotations.with_suffix(args.annotations.suffix + ".pending")
            staged.write_text(json.dumps(annotations, indent=2) + "\n", encoding="utf-8")
            staged.replace(args.annotations)
        print(f"Saved {len(annotations)} manual annotations; hash {digest(annotations)}")
        return
    from sentio.evaluation.evidence_model import run_experiment

    run_experiment(corpus, pack, annotations, args.output, track=args.mlflow)


if __name__ == "__main__":
    main()
