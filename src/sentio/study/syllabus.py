"""A course syllabus: its units and topics, matched to the topics of the student's lectures.

Parsing and matching are deterministic. A syllabus topic matches a lecture topic when its
words appear in that topic's title (weighted double) or slide text; the status of a
syllabus topic comes from the practice state of the lecture topics it matches.
"""

import re
from collections import Counter

MAX_ITEM = 120
MAX_LINKS = 3
MATCH_THRESHOLD = 0.6
STRONG_TEXT_MATCH = 0.75

_UNIT = re.compile(
    r"^(unit|module|chapter|part|section|week|topic)\s*[-:.#]?\s*([0-9]+|[ivxlc]+)\b[\s\-:.–—)]*(.*)$",
    re.IGNORECASE,
)
_SKIP_SECTION = re.compile(
    r"^(text\s*-?\s*books?|reference(s| books?)?|suggested readings?|course outcomes?|"
    r"learning outcomes?|outcomes?|assessment|evaluation( scheme)?|web resources|"
    r"studio work|lab(oratory)?|practicals?|list of (experiments|practicals))\b",
    re.IGNORECASE,
)
_NOISE = re.compile(
    r"^(l\s*t\s*p(\s*c)?|credits?|total|hours?|contact hours|course code|prerequisites?|"
    r"course objectives?|objectives?|syllabus)\b",
    re.IGNORECASE,
)
_HOURS = re.compile(
    r"[\(\[]\s*\d+\s*(lectures?\s*)?(hours?|hrs?|lectures?|periods?|l)\s*[\)\]]"
    r"|\b\d+\s*(lectures?\s*)?(hours?|hrs?|lectures?|periods?)\s*$",
    re.IGNORECASE,
)
_BULLET = re.compile(
    r"^([\-\*•▪●◦·▸➢]|\(?\d+(\.\d+)*[.)]|\(?[a-z][.)]|\(?[ivx]+[.)])\s+", re.IGNORECASE
)
_WORD = re.compile(r"[A-Za-z0-9]+")
_SAME = {w: "versus" for w in ("vs", "versus", "comparison", "compare", "contrast", "difference")}
_STOP = {
    "the", "and", "for", "with", "its", "their", "from", "into", "using", "use", "via",
    "introduction", "intro", "basic", "basics", "concept", "concepts", "overview",
    "types", "various", "different", "study", "applications", "application", "unit",
    "module", "chapter", "part",
}  # fmt: skip


_COMMON = {"and", "as", "at", "by", "for", "from", "in", "is", "of", "on", "or", "the", "to"}


def vocabulary(texts):
    """Words a syllabus title may be repaired towards: the course's own, plus common ones."""
    return _COMMON | {
        word.casefold() for text in texts for word in _WORD.findall(text or "") if len(word) >= 3
    }


def _known(word, words):
    return word in words or (word.endswith("s") and word[:-1] in words)


def repair_title(title, words=frozenset()):
    """Undo PDF damage: "a nd", "probl ems", "toggle -switches" and "Booth�s"."""
    title = re.sub(r"(\w)\ufffds\b", r"\1's", title)
    title = re.sub(r"(\w) -(\w)", r"\1-\2", title)
    parts = title.split(" ")
    repaired = []
    for part in parts:
        before = repaired[-1] if repaired else ""
        joined = (before + part).casefold()
        fragment = not (before.casefold() in words and part.casefold() in words)
        if before.isalpha() and part.isalpha() and fragment and _known(joined, words):
            repaired[-1] = before + part
        else:
            repaired.append(part)
    return " ".join(repaired)


def _clean(text):
    text = _HOURS.sub("", " ".join(text.split())).strip(" .;:,-–—")
    return _BULLET.sub("", text).strip(" .;:,-–—")


def _split(text):
    parts = [_clean(part) for part in re.split(r"[;,]", text)]
    return [part[:MAX_ITEM] for part in parts if len(part) >= 3 and not part.isdigit()]


def _join(lines):
    """Rejoin a paragraph wrapped across lines; "Small-" + "scale" becomes "Small-scale"."""
    text = ""
    for line in lines:
        text = text + line if text.endswith("-") else f"{text} {line}".strip()
    return text


def _body_items(unit, lines):
    lines = [line for line in lines if not _NOISE.match(line)]
    joined = _join(lines)
    listed = joined.count(",") + joined.count(";")
    if lines and listed >= len(lines) - 1 and not any(_BULLET.match(line) for line in lines[1:]):
        return [{"unit": unit, "title": title} for title in _split(joined)]
    items = []
    for line in lines:
        cleaned = _clean(line)
        titles = _split(cleaned) if ("," in cleaned or ";" in cleaned) else [cleaned[:MAX_ITEM]]
        items += [{"unit": unit, "title": title} for title in titles if len(title) >= 3]
    return items


def parse_syllabus(text, words=frozenset()):
    """[{"unit": label or None, "title": topic, "hours": unit hours or None}] in syllabus order.

    `words` is the vocabulary used to repair words a PDF split in two.
    """
    lines = [" ".join(line.split()) for line in (text or "").splitlines()]
    lines = [line for line in lines if line]
    has_units = any(_UNIT.match(line) for line in lines)
    items, unit, unit_name, body, skipping = [], None, None, [], False
    hours = {}

    def close():
        items.extend(_body_items(unit, body))
        _close_unit(items, unit, unit_name)

    for line in lines:
        header = _UNIT.match(line)
        if header:
            close()
            skipping, unit_name, body = False, None, []
            label = f"{header[1].title()} {header[2].upper()}"
            stated = _HOURS.search(header[3])
            rest = _clean(_HOURS.sub("", header[3]))
            # "Memory Management – Paging, Segmentation": a unit name, then its topics.
            parts = re.split(r"\s+[–—-]\s+|:\s*", rest, maxsplit=1)
            name, listed = (parts[0], parts[1]) if len(parts) == 2 else (rest, "")
            if listed and ("," in listed or ";" in listed):
                unit = f"{label}: {name}" if name else label
                body = [listed]
            elif "," in rest or ";" in rest:
                unit, body = label, [rest]
            else:
                unit = f"{label}: {rest}" if rest else label
                unit_name = rest
            if stated:
                hours[unit] = int(re.search(r"\d+", stated[0])[0])
            continue
        if _SKIP_SECTION.match(line):
            skipping = True
            continue
        if not skipping and not (has_units and unit is None):
            body.append(line)
    close()
    return [
        {**item, "title": repair_title(item["title"], words), "hours": hours.get(item["unit"])}
        for item in items
    ]


def _close_unit(items, unit, name):
    """A named unit with no listed topics ("Module 2 - Deadlocks") is itself one topic."""
    if name and not any(item["unit"] == unit for item in items):
        items.append({"unit": unit, "title": name[:MAX_ITEM]})


def _words(text):
    """Comparable words: lower case, singular, with "vs"/"comparison" treated as one word.
    Two-letter words count only as acronyms ("AI", "IO")."""
    words = set()
    for original in _WORD.findall(text or ""):
        word = original.casefold()
        word = _SAME.get(word, word)
        if (len(word) < 3 and not (len(word) == 2 and original.isupper())) or word in _STOP:
            continue
        if word.endswith("ies") and len(word) > 4:
            word = word[:-3] + "y"
        elif word.endswith("s") and not word.endswith("ss") and len(word) > 4:
            word = word[:-1]
        words.add(word)
    return words


def match(title, topics):
    """Ids of the lecture topics a syllabus topic matches, best first.

    Each syllabus word scores 2 if it is in a topic's title, 1 if only in its slide text.
    A topic matches when it reaches MATCH_THRESHOLD of the maximum and shares a title word, or
    reaches STRONG_TEXT_MATCH from slide text alone (a single word mentioned in passing is
    not enough). Matches well below the best one are dropped.
    """
    wanted = _words(title)
    if not wanted:
        return []
    scored = []
    for topic in topics:
        in_title = _words(topic["title"])
        in_text = _words(topic.get("text", ""))
        score = sum(2 if w in in_title else 1 if w in in_text else 0 for w in wanted)
        score /= 2 * len(wanted)
        if score >= MATCH_THRESHOLD and (wanted & in_title or score >= STRONG_TEXT_MATCH):
            scored.append((score, topic["id"]))
    scored.sort(key=lambda pair: -pair[0])
    best = scored[0][0] if scored else 0
    return [topic_id for score, topic_id in scored[:MAX_LINKS] if score >= best - 0.25]


def item_status(states):
    """Status of a syllabus topic from the states of the lecture topics it matches."""
    if not states:
        return "no_notes"
    if all(state == "ready" for state in states):
        return "ready"
    if all(state in ("ready", "review_due") for state in states):
        return "review_due"
    if all(state == "not_started" for state in states):
        return "not_started"
    return "practising"


def item_weights(items):
    """Each item's share of its unit's teaching hours; equal unless every unit states hours."""
    sizes = Counter(item["unit"] for item in items)
    if not all(item.get("unit_hours") for item in items):
        return [1] * len(items)
    return [item["unit_hours"] / sizes[item["unit"]] for item in items]


def summarise(statuses, weights=None):
    names = ("ready", "review_due", "practising", "not_started", "no_notes")
    counts = {status: statuses.count(status) for status in names}
    weights = weights or [1] * len(statuses)
    ready = sum(weight for status, weight in zip(statuses, weights) if status == "ready")
    return {
        **counts,
        "total": len(statuses),
        "percent_ready": round(100 * ready / sum(weights)) if statuses else 0,
    }
