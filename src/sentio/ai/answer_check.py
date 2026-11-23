"""Check a generated answer sentence by sentence against the passages it was given.

One review replaces several separate checks that judged the answer as a whole (a
citation present, word overlap averaged over the answer, refusals recognised by fixed
opening phrases). Judging the whole answer let an invented sentence pass inside a
copied one and rejected correct paraphrases; it also threw away correct partial
answers because of one hedging sentence.

The review keeps what the notes support, drops what they don't, keeps the model's
own statement of what is missing, and says which of these happened:

- answered: every sentence with content is supported.
- partial: some supported content, plus either a stated gap or dropped sentences.
- not_in_notes: nothing supported and the model said the notes lack it.
- unverified: nothing supported and no stated gap (the answer cannot be shown).
"""

import re
from dataclasses import dataclass, field

from sentio.ai.grounding import content_words, split_page_lists

CITATION = re.compile(r"\[([^\[\]\n]*?)\s+Page\s+(\d+|N/A)\]")
LINE_BREAK = "\n"

# A sentence saying the notes lack something: a negation near a word for the notes.
_NEGATION = (
    r"(?:do(?:es)?\s*n[o']t|don't|doesn't|did\s*n[o']t|is\s*n[o']t|are\s*n[o']t|"
    r"not\s+(?:mention|cover|include|specify|provide|contain|state|say|give|explain|define)|"
    r"no\s+(?:information|mention|details?|data)|lacks?|without\s+(?:any\s+)?mention|"
    r"neither\b[^.?!\n]{0,60}\bnor\b[^.?!\n]{0,60}\bcover)"
)
_NOTES = (
    r"(?:notes?|passages?|slides?|sources?|material|lectures?|documents?|provided\s+text|context)"
)
GAP = re.compile(
    rf"\b{_NOTES}\b[^.?!\n]{{0,80}}?\b{_NEGATION}|\b{_NEGATION}\b[^.?!\n]{{0,80}}?\b{_NOTES}\b",
    re.IGNORECASE,
)
CLARIFY = re.compile(r"^\s*(?:could|can|do|did|would) you (?:clarify|mean|specify)", re.IGNORECASE)

# Facts a small model adds from memory: years, decades, percentages and proper names.
YEAR = re.compile(r"\b(?:1[5-9]\d\d|20\d\d)s?\b")
PERCENT = re.compile(r"\b\d+(?:\.\d+)?\s?%")
NAME = re.compile(r"\b[A-Z][a-z]{2,}(?:[- ][A-Z][a-z]{2,})*\b")
# Words a sentence may capitalise without naming anything.
COMMON_CAPITALS = frozenset(
    "the this that these those there here what when where which while with without for "
    "from into about after before because since also however therefore thus then first "
    "second third finally sure yes let lets note step steps example examples imagine "
    "think now next last both each other another in on at by to of as if so it its "
    "you your we our they their he she his her an and or but not no all any some".split()
)

# A sentence counts as supported when this share of its content words occurs in the
# passages (or in the tutor's previous checked answer, for a re-explanation).
MIN_SENTENCE_SUPPORT = 0.5
# Short connective sentences ("Let's break it down.") carry no claim worth checking.
MIN_CHECKED_WORDS = 3
# A sentence is checked when it adds at least this many content words beyond the question.
MIN_ADDED_WORDS = 2
# A long sentence with at least this many words found in the notes needs a lower share.
MIN_MATCHED_WORDS = 5
MIN_LONG_SENTENCE_SUPPORT = 0.35
# Where a refusal sentence turns into an answer from memory.
PIVOT = re.compile(r",?\s+\b(?:but|however|although|though|yet)\b|;", re.IGNORECASE)


@dataclass
class Review:
    text: str
    status: str
    dropped: list = field(default_factory=list)
    reason: str = ""


def _mask_brackets(text):
    """Hide [...] so a filename like "[4. Intro.pdf Page 3]" never ends a sentence."""
    saved = []

    def keep(match):
        saved.append(match.group(0))
        return "\x00" + str(len(saved) - 1) + "\x00"

    return re.sub(r"\[[^\[\]\n]*\]", keep, text), saved


def _unmask(text, saved):
    return re.sub("\x00(\\d+)\x00", lambda m: saved[int(m.group(1))], text)


SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9(\"'*\-•])")


def units(text):
    """Sentences of each line, brackets kept intact; LINE_BREAK items mark line breaks."""
    masked, saved = _mask_brackets(text)
    out = []
    for index, line in enumerate(masked.split(LINE_BREAK)):
        if index:
            out.append(LINE_BREAK)
        if line.strip():
            out += [_unmask(sentence, saved) for sentence in SENTENCE_END.split(line.strip())]
    return out


def _join(parts):
    text = ""
    for part in parts:
        if part == LINE_BREAK:
            text = text.rstrip(" ") + LINE_BREAK
        else:
            text += ("" if not text or text.endswith(LINE_BREAK) else " ") + part.strip()
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def is_gap(sentence):
    return bool(GAP.search(CITATION.sub(" ", sentence)))


SUFFIXES = (
    "ations",
    "ation",
    "ions",
    "ion",
    "ings",
    "ing",
    "ers",
    "er",
    "ies",
    "es",
    "ed",
    "ly",
    "s",
)


def stem(word):
    """A light stem so "separates", "separator" and "separated" compare equal."""
    for suffix in SUFFIXES:
        if len(word) - len(suffix) >= 4 and word.endswith(suffix):
            return word[: -len(suffix)]
    return word


def stems(text):
    return {stem(word) for word in content_words(text)}


def _checked_words(sentence):
    """The stems a sentence claims something with, or an empty set when it claims nothing.

    Questions back to the learner and lead-ins ending in a colon make no claim.
    """
    body = CITATION.sub(" ", sentence).strip()
    if body.endswith("?") or body.endswith(":"):
        return set()
    words = stems(body)
    return words if len(words) >= MIN_CHECKED_WORDS else set()


def is_refusal(text):
    """The reply says the notes lack the answer and claims nothing else."""
    parts = [u for u in units(text or "") if u != LINE_BREAK]
    claims = [u for u in parts if not is_gap(u) and _checked_words(u)]
    return any(is_gap(u) for u in parts) and not claims


def _known_text(*texts):
    joined = " ".join(t for t in texts if t).lower()
    return re.sub(r"\s+", " ", joined).replace(" %", "%")


def new_facts(sentence, known):
    """Years, percentages and names in the sentence that nothing it was given contains."""
    body = CITATION.sub(" ", sentence)
    found = [m for m in YEAR.findall(body) if m.lower() not in known]
    # "40%" is supported by a table cell "40"; only the number has to be known.
    numbers = set(re.findall(r"\d+(?:\.\d+)?", known))
    found += [m for m in PERCENT.findall(body) if re.match(r"[\d.]+", m).group(0) not in numbers]
    for match in NAME.finditer(body):
        start = match.start()
        before = body[:start].rstrip()
        if not before or before[-1] in ".!?:\"'(*-•" or re.search(r"\d[.)]$", before):
            continue  # a sentence or list item may start with a capital
        words = match.group(0).lower().replace("-", " ").split()
        if any(w not in COMMON_CAPITALS and w not in known for w in words):
            found.append(match.group(0))
    return found


CITATION_TEXT = re.compile(r"\[[^\[\]\n]*?\s+Page\s+(?:\d+|N/A)\]")


def reference(citation):
    return f"[{citation['filename']} Page {citation['page']}]"


def repair_citations(text, citations, prior=""):
    """Keep citations to passages the model was given; cite the best passage if none remain.

    A citation to a page that wasn't retrieved this turn is removed, not treated as a
    reason to discard the whole answer; pages the previous checked answer cited stay
    valid for a follow-up about it.
    """
    allowed = {reference(c) for c in citations} | set(CITATION_TEXT.findall(prior or ""))
    text = CITATION_TEXT.sub(lambda m: m.group(0) if m.group(0) in allowed else "", text)
    text = re.sub(r"[ \t]+([.,;:])", r"\1", re.sub(r"[ \t]{2,}", " ", text)).strip()
    if CITATION.search(text) or not citations:
        return text
    words = stems(CITATION.sub(" ", text))
    scored = sorted(
        ((len(words & stems(str(c.get("text", "")))), i, c) for i, c in enumerate(citations)),
        key=lambda item: (-item[0], item[1]),
    )
    best = [c for score, _, c in scored[:2] if score] or [citations[0]]
    return f"{text} {' '.join(dict.fromkeys(reference(c) for c in best))}"


PARTIAL_NOTE = "Part of my answer wasn't supported by your notes, so I left it out."
UNVERIFIED = "I couldn't write an answer I can check against your notes."
# Shown only when a passage reads as text: OCR of diagrams is mostly symbols.
MIN_READABLE_SHARE = 0.75
MIN_READABLE_WORDS = 8


def readable(text):
    visible = [ch for ch in text if not ch.isspace()]
    letters = sum(ch.isalpha() for ch in visible)
    return len(
        re.findall(r"[A-Za-z]{3,}", text)
    ) >= MIN_READABLE_WORDS and letters >= MIN_READABLE_SHARE * max(1, len(visible))


def honest_fallback(citations, shown=2):
    """What to show when no generated sentence could be checked: say so, then the
    closest readable slides (never unreadable OCR)."""
    clear = [c for c in citations if readable(str(c.get("text", "")))][:shown]
    if not clear:
        pages = ", ".join(dict.fromkeys(reference(c)[1:-1] for c in citations[:shown]))
        tail = f" The closest slides are {pages}, but their text is hard to read." if pages else ""
        return UNVERIFIED + tail
    quoted = [
        "> " + str(c["text"]).strip()[:700].replace("\n", "\n> ") + "\n\n" + reference(c)
        for c in clear
    ]
    return UNVERIFIED + " These slides look closest:\n\n" + "\n\n".join(quoted)


def review(text, passages, question="", prior=""):
    """Keep the supported sentences of `text` and classify the result.

    `passages` are the retrieved passage texts; `prior` is the tutor's previous checked
    answer, which a re-explanation may restate in simpler words.
    """
    text = split_page_lists(text or "").strip()
    evidence = stems(" ".join(passages))
    earlier = stems(prior or "")
    # Words echoed from the question prove nothing: retrieval found these passages
    # because they contain them. A sentence is judged on what it adds.
    asked = stems(question or "")
    known = _known_text(*passages, question, prior)
    kept, dropped, gaps, supported, restated = [], [], [], 0, 0
    for unit in units(text):
        if unit == LINE_BREAK:
            kept.append(unit)
            continue
        if is_gap(unit) or CLARIFY.search(unit):
            # "X is not in these notes, but it was Vapnik in the 1990s": keep the gap,
            # never the remembered answer joined to it.
            if new_facts(unit, known):
                unit = PIVOT.split(unit, maxsplit=1)[0].rstrip(" ,;") + "."
                if new_facts(unit, known):
                    dropped.append(unit)
                    continue
            gaps.append(unit)
            kept.append(unit)
            continue
        claims = _checked_words(unit)
        words = claims - asked
        facts = new_facts(unit, known)
        if len(words) < MIN_ADDED_WORDS and not facts:
            kept.append(unit)  # restates the question or links sentences: no new claim
            restated += bool(claims)
            continue
        matched = max(len(words & evidence), len(words & earlier))
        share = matched / max(1, len(words))
        # A long sentence carries filler words ("makes up", "worth"); many specific
        # matches with the notes still show where it came from.
        grounded = share >= MIN_SENTENCE_SUPPORT or (
            matched >= MIN_MATCHED_WORDS and share >= MIN_LONG_SENTENCE_SUPPORT
        )
        if grounded and not facts:
            supported += 1
            kept.append(unit)
        else:
            dropped.append(unit)
    body = _join(kept)
    content = supported or restated
    if content and not dropped and not gaps:
        return Review(body, "answered")
    if supported or (restated and dropped):
        return Review(body, "partial", dropped)
    if gaps:
        return Review(" ".join(g.strip() for g in gaps), "not_in_notes", dropped)
    return Review("", "unverified", dropped, "No sentence is supported by the retrieved notes")
