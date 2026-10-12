"""Offline annotation UI with no proposed labels or learner data."""

import json
from pathlib import Path

from sentio.evaluation.evidence_dataset import digest, pair_hash


def export_review(corpus, pack, output):
    if pack["corpus_hash"] != digest(corpus):
        raise ValueError("Annotation packet belongs to another corpus")
    output = Path(output)
    if output.exists():
        raise ValueError("Choose a new review file instead of overwriting an existing one")
    questions = {q["question_id"]: q for q in corpus["questions"]}
    documents = {d["document_id"]: d for d in corpus["documents"]}
    for pair in pack["pairs"]:
        if pair["pair_hash"] != pair_hash(
            questions[pair["question_id"]], documents[pair["document_id"]]
        ):
            raise ValueError("Review packet contains stale passage hashes")
    payload = {
        "corpus_hash": digest(corpus),
        "pairs": [
            {
                "pair_id": pair["pair_id"],
                "pair_hash": pair["pair_hash"],
                "split": pair["split"],
                "question": questions[pair["question_id"]]["text"],
                "passage": documents[pair["document_id"]]["text"],
                "title": documents[pair["document_id"]]["title"],
            }
            for pair in pack["pairs"]
        ],
    }
    encoded = json.dumps(payload, ensure_ascii=False).replace("<", "\\u003c")
    template = Path(__file__).with_name("evidence_review.html").read_text(encoding="utf-8")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(template.replace("__REVIEW_PAYLOAD__", encoded), encoding="utf-8")
    return len(payload["pairs"])
