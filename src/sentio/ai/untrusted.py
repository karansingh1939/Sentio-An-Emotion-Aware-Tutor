"""Remove text addressed to the tutor from notes before the model reads them.

Notes are data. A sentence inside them that speaks to the assistant ("SYSTEM: ...",
"ignore the rules above", "reply only ...", "tell the student ...") is an instruction
smuggled into the source, and a 7B model will sometimes obey it, however clearly the
prompt says not to. Such sentences are removed from the passages the model sees, so
it cannot obey or quote them; the rest of the passage is kept.
"""

import logging
import re

logger = logging.getLogger(__name__)

_ACTOR = r"(?:tutor|assistant|ai|model|chatbot|bot|llm)"
ADDRESSED = re.compile(
    "|".join(
        [
            r"^\W*(?:system|assistant|tutor|ai|developer)\s*(?:message|prompt|note)?\s*:",
            r"\b(?:ignore|disregard|forget|override)\b[^.\n]{0,40}\b(?:rules?|instructions?|prompts?|guidelines|notes)\b",
            rf"\binstructions?\s+(?:to|for)\s+(?:the\s+)?{_ACTOR}\b",
            rf"\b(?:dear|attention|note\s+to(?:\s+the)?)\s+{_ACTOR}\b",
            r"\b(?:reply|respond|answer)\s+(?:only|with\s+only|exactly)\b",
            r"\balways\s+(?:end|start|begin|finish)\s+(?:your|every|each)\s+(?:answer|reply|response)",
            r"\b(?:tell|inform)\s+the\s+(?:student|learner|user)\s+that\b",
            rf"\byou\s+are\s+(?:now\s+)?(?:a|an|the)\s+[^.\n]{{0,30}}\b{_ACTOR}\b",
            rf"\bas\s+(?:the|an?)\s+{_ACTOR}\s*,\s*you\b",
        ]
    ),
    re.IGNORECASE | re.MULTILINE,
)
SENTENCE = re.compile(r"[^.!?\n]+[.!?]?\n?|\n")


def strip_instructions(text):
    """The text without sentences addressed to the tutor, and how many were removed."""
    kept, removed = [], 0
    for sentence in SENTENCE.findall(text or ""):
        if ADDRESSED.search(sentence):
            removed += 1
        else:
            kept.append(sentence)
    return "".join(kept).strip(), removed


def clean_passages(content):
    """Strip tutor-addressed sentences from every retrieved passage, in place."""
    citations = getattr(content, "source_citations", None) or []
    removed_total, kept = 0, []
    for citation in citations:
        text, removed = strip_instructions(str(citation.get("text", "")))
        removed_total += removed
        if removed:
            citation["text"] = text
        if text:
            kept.append(citation)
    if removed_total:
        logger.warning("Removed %d instruction-like sentences from retrieved notes", removed_total)
        content.source_citations = kept
        if getattr(content, "rag_context", None):
            content.rag_context = strip_instructions(content.rag_context)[0]
    return removed_total
