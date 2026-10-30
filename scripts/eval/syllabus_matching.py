"""Measure syllabus matching against a student's own labels.

`checklist` writes a local page listing each syllabus item with its likely lecture topics;
the student confirms the right ones and saves a labels file. `evaluate` scores the word
matcher on those labels, and three ways embeddings could improve it, each by nested
cross-validation. Sentio keeps word matching because none of them beat it. Everything stays
on this machine.
"""

import argparse
import json
import random
from pathlib import Path
from statistics import mean

from sentio.config import nlp_cfg
from sentio.ingestion.pipeline import DocumentIngestionPipeline
from sentio.study.syllabus import MAX_LINKS, match, parse_syllabus, vocabulary
from sentio.study.topics import build_topics

PAGE = Path(__file__).with_name("syllabus_checklist.html")
SUGGESTIONS = 5
FOLDS = 5
REPEATS = 20
ADD_AT = (0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8)
FILL_AT = (0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8)
PRUNE_BY = (0.02, 0.05, 0.1, 0.15, 0.2, 0.3)


def lecture_topics(decks):
    topics = []
    for deck in decks:
        pages = DocumentIngestionPipeline.parse_pptx(None, deck)
        pairs = [(page["page_number"], page["text"]) for page in pages]
        for topic in build_topics(pairs, deck.stem):
            first, last = topic["first_page"], topic["last_page"]
            text = "\n".join(body for number, body in pairs if first <= number <= last)
            topics.append(
                {**topic, "id": f"{deck.stem}:{first}", "filename": deck.name, "text": text}
            )
    return topics


def load_course(syllabus, decks):
    topics = lecture_topics(decks)
    pages = DocumentIngestionPipeline.parse_pdf(None, syllabus)
    text = "\n".join(page["text"] for page in pages)
    words = vocabulary(topic["text"] for topic in topics)
    return parse_syllabus(text, words), topics


def encoder():
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(nlp_cfg.EMBEDDING_MODEL, device="cpu", local_files_only=True)
    return lambda texts: model.encode(texts, normalize_embeddings=True)


def topic_passage(topic):
    return f"{topic['title']}. {' '.join(topic['text'].split())[:300]}"


def checklist(args):
    items, topics = load_course(args.syllabus, args.decks)
    encode = encoder()
    similarity = (
        encode([item["title"] for item in items])
        @ encode([topic_passage(topic) for topic in topics]).T
    )
    rows = []
    for position, item in enumerate(items):
        matched = match(item["title"], topics)
        ranked = similarity[position].argsort()[::-1][:SUGGESTIONS]
        likely = [topics[index]["id"] for index in ranked]
        rows.append(
            {
                "position": position,
                "unit": item["unit"],
                "title": item["title"],
                "matched": matched,
                "suggested": list(dict.fromkeys(matched + likely)),
            }
        )
    shown = [
        {key: topic[key] for key in ("id", "title", "filename", "first_page", "last_page")}
        for topic in topics
    ]
    data = json.dumps({"items": rows, "topics": shown}).replace("</", "<\\/")
    args.output.write_text(
        PAGE.read_text(encoding="utf-8").replace("__DATA__", data), encoding="utf-8"
    )
    print(f"{len(rows)} items, {len(topics)} topics. Open {args.output} in a browser.")


def scores(predicted, labels):
    """Precision, recall and F1 over item-to-topic links, and over "is it in the notes"."""
    found = sum(len(set(predicted[item]) & set(truth)) for item, truth in labels.items())
    made = sum(len(predicted[item]) for item in labels)
    wanted = sum(len(truth) for truth in labels.values())
    hits = sum(bool(predicted[item]) and bool(truth) for item, truth in labels.items())
    claimed = sum(bool(predicted[item]) for item in labels)
    covered = sum(bool(truth) for truth in labels.values())

    def measured(correct, predicted_count, actual):
        precision = correct / predicted_count if predicted_count else 0.0
        recall = correct / actual if actual else 0.0
        total = precision + recall
        return {
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "f1": round(2 * precision * recall / total, 3) if total else 0.0,
            "predicted": predicted_count,
            "actual": actual,
        }

    return {"links": measured(found, made, wanted), "in_notes": measured(hits, claimed, covered)}


def load_labels(path):
    """{syllabus position: [topic ids]}, for rows confirmed or written by hand."""
    stored = json.loads(path.read_text(encoding="utf-8"))
    return {row["position"]: row["topics"] for row in stored["items"] if row.get("confirmed", True)}


def with_embeddings(baseline, similar, add=None, fill=None, prune=None):
    """Word matches changed by embedding similarity.

    `add` also links topics at or above a similarity, `fill` links the closest topic only
    when words found nothing, and `prune` drops links this far below the item's best one.
    """
    predicted = {}
    for position, linked in baseline.items():
        row, kept = similar[position], list(linked)
        if prune is not None and kept:
            best = max(row[topic] for topic in kept)
            kept = [topic for topic in kept if row[topic] >= best - prune]
        if add is not None:
            close = sorted((t for t in row if row[t] >= add and t not in kept), key=row.get)
            kept = (kept + close[::-1])[:MAX_LINKS]
        if fill is not None and not kept:
            closest = max(row, key=row.get)
            kept = [closest] if row[closest] >= fill else []
        predicted[position] = kept
    return predicted


def objective(predicted, labels):
    measured = scores(predicted, labels)
    return measured["links"]["f1"] + measured["in_notes"]["f1"]


def nested_score(baseline, labels, candidates):
    """Each item is predicted by the candidate that did best on the other folds, so choosing
    a candidate cannot flatter the score. `baseline` is always among the candidates."""
    candidates = [baseline, *candidates]
    rounds = []
    for seed in range(REPEATS):
        positions = sorted(labels)
        random.Random(seed).shuffle(positions)
        predicted = {}
        for fold in range(FOLDS):
            held_out = set(positions[fold::FOLDS])
            train = {k: v for k, v in labels.items() if k not in held_out}
            chosen = max(candidates, key=lambda candidate: objective(candidate, train))
            predicted.update({position: chosen[position] for position in held_out})
        rounds.append(scores(predicted, labels))
    return {
        group: {
            metric: round(mean(result[group][metric] for result in rounds), 3)
            for metric in ("precision", "recall", "f1")
        }
        for group in ("links", "in_notes")
    }


def evaluate(args):
    items, topics = load_course(args.syllabus, args.decks)
    labels = load_labels(args.labels)
    baseline = {p: match(item["title"], topics) for p, item in enumerate(items)}
    encode = encoder()
    vectors = encode([item["title"] for item in items])
    ids = [topic["id"] for topic in topics]
    sources = [
        {
            position: dict(zip(ids, map(float, row)))
            for position, row in enumerate(vectors @ encode(texts).T)
        }
        for texts in (
            [topic["title"] for topic in topics],
            [topic_passage(topic) for topic in topics],
        )
    ]
    ideas = {
        "add_similar_topics": {"add": ADD_AT},
        "fill_gaps_only": {"fill": FILL_AT},
        "prune_weak_links": {"prune": PRUNE_BY},
    }
    report = {
        "items_labelled": len(labels),
        "items_in_notes": sum(bool(truth) for truth in labels.values()),
        "word_overlap": scores(baseline, labels),
    }
    for idea, settings in ideas.items():
        ((name, values),) = settings.items()
        candidates = [
            with_embeddings(baseline, similar, **{name: value})
            for similar in sources
            for value in values
        ]
        report[idea] = nested_score(baseline, labels, candidates)
    print(json.dumps(report, indent=2))
    if args.output:
        args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["checklist", "evaluate"])
    parser.add_argument("--syllabus", type=Path, required=True)
    parser.add_argument("--decks", type=Path, nargs="+", required=True)
    parser.add_argument("--labels", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.command == "checklist":
        if not args.output:
            parser.error("checklist needs --output")
        checklist(args)
    else:
        if not args.labels:
            parser.error("evaluate needs --labels")
        evaluate(args)


if __name__ == "__main__":
    main()
