"""Topics inside a lecture, and how well each one has been practised.

A topic is a run of consecutive pages (slides for PowerPoint) that share a heading. Quiz
questions are attributed to the page whose passage they best match, so a topic's state
comes from the answers to questions on its pages. Everything here is deterministic.
"""

import re
from collections import Counter

READY_MIN_ANSWERS = 3
READY_RECENT = 3
READY_RECENT_CORRECT = 3
MAX_TITLE = 80
MAX_PRACTICE_TOPICS = 5
MAX_PRACTICE_TEXT = 3000  # Characters of slides in one quiz prompt.

_CONTINUED = re.compile(r"[\s\-–—:.…(\[]*\bcont(inued|'d|d)?\.?[)\]]?\s*$", re.IGNORECASE)
# A sentence break inside a line, but not after an abbreviation ("Hardwired vs. Microprogrammed").
_SENTENCE = re.compile(
    r"(?<!\bvs)(?<!\be\.g)(?<!\bi\.e)(?<!\betc)(?<!\bfig)(?<!\bno)(?<!\bst)[.!?]\s", re.IGNORECASE
)
_CLOSING = re.compile(
    r"^(thank\s*you|thanks|any questions|questions|q\s*&\s*a|the end)\W*$", re.IGNORECASE
)
_PARENS = re.compile(r"\s*\([^)]*\)")
# Lines that mark a deck's cover slide rather than a topic.
_COVER = re.compile(
    r"\b(course\s*code|week\s*\d+|lecture\s*(no\.?\s*)?\d+|semester|instructor|faculty|"
    r"prepared by|presented by|submitted by)\b",
    re.IGNORECASE,
)
MAX_TITLE_WORDS = 10
_NUMBERED = re.compile(r"\s*[\(\[]\d+[\)\]]\s*$|\s*[-–:]\s*(part\s*)?\d+\s*$", re.IGNORECASE)
_PAGE_NUMBER = re.compile(r"^(page\s*)?\d+(\s*(/|of)\s*\d+)?$", re.IGNORECASE)
_WORDS = re.compile(r"[a-z0-9]{3,}")
_STOP = {"the", "and", "for", "are", "with", "that", "this", "from", "which", "what", "into"}


def _candidates(text):
    for line in text.splitlines():
        line = " ".join(line.split())
        if line and not _PAGE_NUMBER.match(line):
            yield line


def _key(title):
    title = _NUMBERED.sub("", _CONTINUED.sub("", title))
    return " ".join(re.sub(r"[-–—_/]", " ", title.casefold()).split())


def _continues(heading, title):
    """The same heading, or a sub-heading of it ("Control Bus- Example" after "Control Bus")."""
    new, base = _key(heading), _key(_PARENS.sub("", title))
    return new == _key(title) or (len(base) >= 3 and re.match(re.escape(base) + r"s?\b", new))


def _heading(text, running):
    """The page's heading: its first short line that is not a running header or page number."""
    for line in _candidates(text):
        if line.casefold() in running:
            continue
        label, _, rest = line.partition(":")
        if (
            len(line) <= MAX_TITLE
            and len(line.split()) <= MAX_TITLE_WORDS
            and not line.endswith((".", "!", ":"))
            and not _SENTENCE.search(line)
            and len(rest.split()) <= 4  # "Peak value: The maximum value of ..." is body text
        ):
            return line
        return None  # The page opens with body text: it continues the previous topic.
    return None


def build_topics(pages, fallback_title):
    """Group ordered (page_number, text) pairs into topics of consecutive pages.

    A line found on most pages (a course name, a footer) is a running header, not a topic.
    Pages without a heading, repeating the previous heading ("Paging (cont.)") or extending
    it ("Control Bus- Example" after "Control Bus") continue the current topic. A short
    cover slide and closing slides ("Thank You", "Questions?") are not topics.
    """
    pages = [(number, text) for number, text in pages if text.strip()]
    if not pages:
        return []
    seen = Counter(line.casefold() for _, text in pages for line in set(_candidates(text)))
    running = {line for line, count in seen.items() if len(pages) >= 4 and count > len(pages) / 2}
    if len(pages) > 2 and _COVER.search(pages[0][1]):
        pages = pages[1:]
    topics = []
    for number, text in pages:
        heading = _heading(text, running)
        if heading and _CLOSING.match(heading):
            continue
        if topics and (heading is None or _continues(heading, topics[-1]["title"])):
            topics[-1]["last_page"] = number
            continue
        title = heading or (topics[-1]["title"] if topics else fallback_title)
        topics.append({"title": title[:MAX_TITLE], "first_page": number, "last_page": number})
    return topics


def _words(text):
    return {word for word in _WORDS.findall((text or "").casefold()) if word not in _STOP}


def fit_pages(pages, budget):
    """(page, text) pairs spread evenly across a topic, within a budget of characters."""
    total = sum(len(text) for _, text in pages)
    keep = max(1, len(pages) * budget // total) if total > budget else len(pages)
    fitted = []
    for index in range(keep):
        page, text = pages[index * len(pages) // keep]
        if budget > 0:
            fitted.append((page, text[:budget]))
            budget -= len(text)
    return fitted


def _asked(question):
    return _words(
        " ".join(
            str(question.get(field) or "")
            for field in ("question_text", "correct_answer", "explanation")
        )
    )


def _overlap(question, citation):
    return len(_asked(question) & _words(citation.get("text")))


def _best_overlap(question, citations):
    """The passage sharing the most words with a question; ties keep the higher-ranked one."""
    best, best_score = None, 0
    for citation in citations:
        score = _overlap(question, citation)
        if score > best_score:
            best, best_score = citation, score
    return best


def place(citation):
    """The (document_id, page) of a passage, or (None, None) without a document."""
    if citation is None or not citation.get("document_id"):
        return None, None
    try:
        return citation["document_id"], int(citation["page"])
    except (TypeError, ValueError):
        return citation["document_id"], None


def attribute(question, citations):
    """The (document_id, page) of the retrieved passage that best matches a question."""
    return place(_best_overlap(question, citations))


def locate(question, citations, topic=None):
    """The passage a question came from, and how that was decided.

    The model names a passage by its Citation Index. That is kept when the passage exists
    and shares at least half as many words with the question as the best match does.
    Otherwise the best word overlap decides, among `topic` (the passages of the topic the
    question was asked for) when given; a question asked for a topic stays in that topic
    even when nothing overlaps.
    """
    index = question.get("source")
    if isinstance(index, int) and 1 <= index <= len(citations):
        named = _overlap(question, citations[index - 1])
        strongest = _best_overlap(question, citations)
        if named and 2 * named >= _overlap(question, strongest):
            return citations[index - 1], "model"
    best = _best_overlap(question, topic or citations)
    if best is not None:
        return best, "overlap"
    return (topic[0], "topic") if topic else (None, "none")


def topic_state(results):
    """State of a topic from its answers in time order (True = correct)."""
    recent = results[-READY_RECENT:]
    correct = sum(recent)
    if not results:
        state = "not_started"
    elif len(results) >= READY_MIN_ANSWERS and correct >= READY_RECENT_CORRECT:
        state = "ready"
    else:
        state = "practising"
    return {
        "state": state,
        "answers": len(results),
        "recent_correct": correct,
        "recent_total": len(recent),
    }


def is_weak(topic):
    """Practised, with a wrong answer among the recent ones."""
    return (
        topic["state"] == "practising"
        and topic["recent_total"] > 0
        and topic["recent_correct"] / topic["recent_total"] < READY_RECENT_CORRECT / READY_RECENT
    )
