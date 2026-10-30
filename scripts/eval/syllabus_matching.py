"""Measure syllabus matching against a student's own labels.

`checklist` writes a local page listing each syllabus item with its likely lecture topics;
the student confirms the right ones and saves a labels file. `evaluate` then scores the
matcher on those labels. Everything stays on this machine.
"""

import argparse
import json
from pathlib import Path

from sentio.config import nlp_cfg
from sentio.ingestion.pipeline import DocumentIngestionPipeline
from sentio.study.syllabus import match, parse_syllabus, vocabulary
from sentio.study.topics import build_topics

PAGE = Path(__file__).with_name("syllabus_checklist.html")
SUGGESTIONS = 5


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
    found = sum(len(set(predicted[title]) & set(truth)) for title, truth in labels.items())
    made = sum(len(predicted[title]) for title in labels)
    wanted = sum(len(truth) for truth in labels.values())
    hits = sum(bool(predicted[title]) and bool(truth) for title, truth in labels.items())
    claimed = sum(bool(predicted[title]) for title in labels)
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


def load_labels(path, items):
    stored = json.loads(path.read_text(encoding="utf-8"))
    titles = {item["title"] for item in items}
    labels = {
        row["title"]: row["topics"]
        for row in stored["items"]
        if row.get("confirmed") and row["title"] in titles
    }
    if not labels:
        raise SystemExit("No confirmed labels match this syllabus.")
    return labels


def evaluate(args):
    items, topics = load_course(args.syllabus, args.decks)
    labels = load_labels(args.labels, items)
    predicted = {item["title"]: match(item["title"], topics) for item in items}
    report = {"items_labelled": len(labels), "word_overlap": scores(predicted, labels)}
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
