"""Search text for a chat turn, and merging of two retrievals by rank."""

import re
from copy import copy

# A query longer than this many words is cut: padding drowns the real question.
MAX_QUERY_WORDS = 60
# Reciprocal-rank fusion constant: rank 1 scores 1/61, rank 5 scores 1/65.
RRF_K = 60
KEPT = 5


def search_text(message):
    """The message without repeated sentences, cut to MAX_QUERY_WORDS words.

    A question followed by a sentence pasted a hundred times embeds and keyword-scores
    as the pasted sentence; each distinct sentence now counts once.
    """
    seen, kept = set(), []
    for sentence in re.split(r"(?<=[.!?])\s+|\n+", message or ""):
        key = re.sub(r"\W+", " ", sentence).strip().lower()
        if key and key not in seen:
            seen.add(key)
            kept.append(sentence.strip())
    words = " ".join(kept).split()
    return " ".join(words[:MAX_QUERY_WORDS])


def _key(citation):
    return citation.get("chunk_id") or (
        citation.get("filename"),
        citation.get("page"),
        str(citation.get("text", ""))[:80],
    )


def _retrieved(content):
    return getattr(content, "evidence_outcome", "") == "retrieved" and bool(
        getattr(content, "source_citations", None)
    )


def merge_rankings(alone, joined, kept=KEPT):
    """One ranking from the message-alone and topic-joined retrievals.

    Passages found by both rank first; ties follow the topic-joined order, which
    carries the conversation's context.
    """
    if not _retrieved(joined):
        return alone
    if not _retrieved(alone):
        return joined
    scores, items, joined_rank = {}, {}, {}
    for content in (alone, joined):
        for rank, citation in enumerate(content.source_citations):
            key = _key(citation)
            scores[key] = scores.get(key, 0.0) + 1.0 / (RRF_K + rank + 1)
            items.setdefault(key, citation)
            if content is joined:
                joined_rank[key] = rank
    order = sorted(scores, key=lambda k: (-scores[k], joined_rank.get(k, len(scores))))[:kept]
    merged = copy(joined)
    merged.source_citations = [items[k] for k in order]
    merged.chunks_used = [c.get("chunk_id") for c in merged.source_citations if c.get("chunk_id")]
    merged.rag_context = "\n".join(
        f"[Document: {c['filename']} | Page: {c['page']} | Citation Index: {i + 1}]\n{c.get('text', '')}\n"
        for i, c in enumerate(merged.source_citations)
    )
    return merged


def stands_alone(alone, joined, merged):
    """Whether the message found its own subject: its top passage leads the merged
    ranking, and the topic-joined search found that passage too."""
    if not _retrieved(alone) or not getattr(merged, "source_citations", None):
        return False
    top = _key(alone.source_citations[0])
    found_with_topic = {_key(c) for c in getattr(joined, "source_citations", None) or []}
    return top == _key(merged.source_citations[0]) and top in found_with_topic
