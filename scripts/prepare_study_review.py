"""Create an offline human-review packet from real recorded tutor responses."""

import argparse
import hashlib
import json
import re
from pathlib import Path

from sentio.evaluation.evidence_dataset import digest, pair_hash
from sentio.evaluation.evidence_review import export_review


def prepare(dataset_path, report_path, output):
    raw = Path(dataset_path).read_bytes()
    dataset = json.loads(raw)
    report = json.loads(Path(report_path).read_text(encoding="utf-8"))["grounding_evaluation"]
    if report["dataset_sha256"] != hashlib.sha256(raw).hexdigest():
        raise ValueError("Report and source dataset do not match")
    documents = [
        {"document_id": name, "title": name, "text": text}
        for name, text in dataset["documents"].items()
    ]
    lookup = {doc["document_id"]: doc for doc in documents}
    questions, pairs = [], []
    for row in report["cases"]:
        response = row.get("response", {}).get("text")
        if not response:
            continue
        question = {
            "question_id": row["case_id"],
            "text": f"Original question: {row['question']}\n\nRecorded reply: {response}\n\nDoes this reply appropriately address the question using only the notes? An abstention is appropriate only when the notes cannot answer. Reject unsupported added facts or a guessed ambiguous referent.",
        }
        questions.append(question)
        pairs.append(
            {
                "pair_id": row["case_id"],
                "pair_hash": pair_hash(question, lookup[row["document"]]),
                "question_id": row["case_id"],
                "document_id": row["document"],
                "split": "train",
            }
        )
    corpus = {"documents": documents, "questions": questions}
    count = export_review(corpus, {"corpus_hash": digest(corpus), "pairs": pairs}, output)
    output = Path(output)
    text = output.read_text(encoding="utf-8")
    text = text.replace(
        "Can these notes answer the question?", "Is this recorded tutor reply appropriate?"
    )
    text = text.replace("Sentio evidence review", "Sentio recorded-answer review")
    text = re.sub(
        r'<section aria-labelledby="guide">.*?</section>',
        """<section aria-labelledby="guide"><h2 id="guide">Review the actual reply</h2>
<ol><li>Read the original question, recorded reply, and full notes below.</li><li>Accept only if the reply addresses the question without unsupported added facts. Accept an abstention only when the notes genuinely lack the answer.</li><li>Reject invented facts, unjustified refusals, or guesses about an ambiguous referent. Explain the exact supporting sentence or problem. Skip if unsure.</li></ol>
<p class="muted">This is author review of synthetic examples, not independent validation or classifier training. No decisions are prefilled.</p></section>""",
        text,
        flags=re.DOTALL,
    )
    text = re.sub(
        r"<p>This is label review.*?</p>",
        "<p>Judge recorded tutor replies against their source notes. Your decisions remain private until you choose to share them.</p>",
        text,
        flags=re.DOTALL,
    )
    text = re.sub(
        r'<select id="split">.*?</select>',
        '<select id="split"><option value="train">Recorded replies</option></select>',
        text,
        flags=re.DOTALL,
    )
    text = text.replace("Enough evidence</button>", "Accept reply</button>").replace(
        "Missing evidence</button>", "Reject reply</button>"
    )
    output.write_text(text, encoding="utf-8")
    return count


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(
        f"Prepared {prepare(args.dataset, args.report, args.output)} replies for human review; no labels created."
    )
