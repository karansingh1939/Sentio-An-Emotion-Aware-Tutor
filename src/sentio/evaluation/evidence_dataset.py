"""Frozen source/question contracts and auditable manual passage annotations."""

import hashlib
import json
import re
from pathlib import Path


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def tokens(text):
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def validate_corpus(corpus):
    documents = corpus["documents"]
    questions = corpus["questions"]
    if len(documents) < 30 or len(questions) < 120:
        raise ValueError("The portfolio corpus requires at least 30 documents and 120 questions")
    topics = corpus["splits"]
    if {name: len(value) for name, value in topics.items()} != {
        "train": 6,
        "validation": 2,
        "test": 2,
    }:
        raise ValueError("Require a topic-disjoint 6/2/2 split")
    flattened = [topic for values in topics.values() for topic in values]
    if len(set(flattened)) != 10:
        raise ValueError("A topic crosses splits")
    ids = [d["document_id"] for d in documents]
    if len(set(ids)) != len(ids) or len({q["question_id"] for q in questions}) != len(questions):
        raise ValueError("Duplicate source or question IDs")
    sources = {d["document_id"]: d for d in documents}
    for item in documents + questions:
        if item["topic"] not in topics[item["split"]]:
            raise ValueError("Topic/source split leakage")
    for question in questions:
        source = sources[question["variant_group"]]
        if question["split"] != source["split"]:
            raise ValueError("Question variants cross source splits")
        if any(sources[d]["split"] != question["split"] for d in question["proposed_support"]):
            raise ValueError("Support source crosses splits")
    for items in (documents, questions):
        for index, left in enumerate(items):
            a = tokens(left["text"])
            for right in items[index + 1 :]:
                if left["split"] == right["split"]:
                    continue
                b = tokens(right["text"])
                if a and b and len(a & b) / len(a | b) >= 0.9:
                    raise ValueError("Near-duplicate text crosses splits")


def freeze_corpus(corpus, destination):
    validate_corpus(corpus)
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    payload = destination / "corpus.json"
    manifest = destination / "manifest.json"
    value = {
        "version": 1,
        "corpus_hash": digest(corpus),
        "test_hash": digest(
            {
                "documents": [d for d in corpus["documents"] if d["split"] == "test"],
                "questions": [q for q in corpus["questions"] if q["split"] == "test"],
            }
        ),
        "splits": corpus["splits"],
        "labels": "unreviewed",
        "duplicate_check": "cross-split token-set Jaccard >= 0.9",
    }
    if manifest.exists() or payload.exists():
        raise ValueError("A frozen corpus cannot be overwritten; create a new version")
    payload.write_text(json.dumps(corpus, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    manifest.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    return value


def load_corpus(directory):
    directory = Path(directory)
    corpus = json.loads((directory / "corpus.json").read_text(encoding="utf-8"))
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    validate_corpus(corpus)
    if digest(corpus) != manifest["corpus_hash"]:
        raise ValueError("Frozen corpus changed; use a new dataset version")
    test = {
        "documents": [d for d in corpus["documents"] if d["split"] == "test"],
        "questions": [q for q in corpus["questions"] if q["split"] == "test"],
    }
    if digest(test) != manifest["test_hash"]:
        raise ValueError("Frozen test split changed")
    return corpus, manifest


def pair_hash(question, document):
    return digest(
        {
            "question": question["text"],
            "passage": document["text"],
            "question_id": question["question_id"],
            "document_id": document["document_id"],
        }
    )


def reviewed_labels(corpus, pairs, annotations):
    questions = {q["question_id"]: q for q in corpus["questions"]}
    documents = {d["document_id"]: d for d in corpus["documents"]}
    by_id = {}
    for annotation in annotations:
        key = annotation["pair_id"]
        if key in by_id:
            raise ValueError("Duplicate annotation receipt")
        by_id[key] = annotation
    labels = []
    for pair in pairs:
        question, document = questions[pair["question_id"]], documents[pair["document_id"]]
        if question["split"] != document["split"]:
            raise ValueError("Retrieved pair crosses source splits")
        annotation = by_id.get(pair["pair_id"])
        if not annotation or annotation.get("review_status") != "human_reviewed":
            raise ValueError("Manual review required: AI-proposed labels cannot train this model")
        if annotation.get("pair_hash") != pair_hash(question, document):
            raise ValueError("Annotation refers to changed question/passage text")
        if (
            not str(annotation.get("reviewer", "")).strip()
            or len(str(annotation.get("rationale", "")).strip()) < 10
        ):
            raise ValueError("Reviewed labels require a named reviewer and written rationale")
        if type(annotation.get("label")) is not int or annotation["label"] not in (0, 1):
            raise ValueError("Evidence label must be zero or one")
        labels.append(annotation["label"])
    return labels
