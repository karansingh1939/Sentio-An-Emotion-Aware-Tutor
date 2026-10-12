"""Deterministic source recall when local generation cannot be validated."""

import re


def source_recall(content, count):
    items = []
    seen = set()
    for citation in getattr(content, "source_citations", []):
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
                items.append(
                    {
                        "question_text": "Complete the sentence from your notes:\n" + blank,
                        "question_type": "fill_in_the_blank",
                        "correct_answer": answer,
                        "explanation": f'Your notes say: "{sentence}" {reference}',
                    }
                )
                # Prefer different passages before making another blank in this one.
                break
    if len(items) < count:
        raise ValueError(
            "Not enough readable source sentences for this practice batch. Choose fewer items or add more notes."
        )
    return items[:count]


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
