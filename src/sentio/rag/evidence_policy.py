"""Conservative retrieval relevance signals, never an answer-correctness probability."""

import re

MIN_DENSE_SIMILARITY = 0.35
FUNCTION_WORDS = set(
    "a an and are as at be by can could do does explain for from how i in is it me of on or please that the their them there these they this to was what when where which who why with would you your".split()
)


def content_terms(text):
    return {
        word
        for word in re.findall(r"[a-z0-9]+", text.lower())
        if len(word) > 1 and word not in FUNCTION_WORDS
    }


def has_relevance_signal(question, passage, vector_score=0):
    return (
        bool(content_terms(question) & content_terms(passage))
        or vector_score >= MIN_DENSE_SIMILARITY
    )
