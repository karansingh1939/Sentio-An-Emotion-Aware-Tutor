"""Deterministic source recall when local generation cannot be validated."""

import re
import time
from itertools import zip_longest


def source_recall(content, count):
    batches = {}
    seen = set()
    for position, citation in enumerate(getattr(content, "source_citations", []), 1):
        batch = batches.setdefault(citation.get("topic_id", position), [])
        for sentence in re.split(r"(?<=[.!?])\s+|\n+", citation.get("text", "")):
            sentence = sentence.strip()
            if not 16 <= len(sentence) <= 700:
                continue
            words = list(re.finditer(r"\b[A-Za-z][A-Za-z'-]{3,}\b", sentence))
            words.sort(key=lambda word: len(word.group()), reverse=True)
            for word in words:
                answer = word.group()
                identity = (sentence, answer.lower())
                if identity in seen:
                    continue
                seen.add(identity)
                blank = sentence[: word.start()] + "_____" + sentence[word.end() :]
                reference = f"[{citation['filename']} Page {citation['page']}]"
                batch.append(
                    {
                        "question_text": "Complete the sentence from your notes:\n" + blank,
                        "question_type": "fill_in_the_blank",
                        "correct_answer": answer,
                        "explanation": f'Your notes say: "{sentence}" {reference}',
                        "source": position,
                    }
                )
                break  # One blank per sentence.
    # One from each passage (or topic) in turn, so each is covered before any repeats.
    items = [item for turn in zip_longest(*batches.values()) for item in turn if item]
    if len(items) < count:
        raise ValueError(
            "Not enough readable source sentences for this practice batch. Choose fewer items or add more notes."
        )
    return items[:count]


def practice_provenance(mode, content, backend, snapshot=None):
    """Record how saved practice was made: generation mode, model, passages and note versions."""
    sources, seen = [], set()
    for citation in getattr(content, "source_citations", []) or []:
        identity = (citation.get("filename"), citation.get("page"))
        if identity in seen:
            continue
        seen.add(identity)
        sources.append(
            {
                "filename": citation.get("filename"),
                "page": citation.get("page"),
                "chunk_id": citation.get("chunk_id"),
            }
        )
    model = getattr(backend, "name", None)
    return {
        "mode": mode,
        "model": model if isinstance(model, str) else type(backend).__name__,
        "sources": sources,
        "documents": (snapshot or {}).get("documents", []),
        "edited": False,
        "created_at": time.time(),
    }


def source_excerpt(content):
    parts = []
    for citation in getattr(content, "source_citations", [])[:2]:
        excerpt = citation.get("text", "")[:1000].strip()
        if excerpt:
            parts.append(
                "> "
                + excerpt.replace("\n", "\n> ")
                + f"\n\n[{citation['filename']} Page {citation['page']}]"
            )
    if not parts:
        raise ValueError("No readable source excerpt is available.")
    return (
        "I could not verify a generated explanation. Here are passages from your notes that may help:\n\n"
        + "\n\n".join(parts)
    )
