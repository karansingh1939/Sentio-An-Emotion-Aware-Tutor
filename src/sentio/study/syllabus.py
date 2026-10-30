"""A course syllabus: its units and topics, matched to the topics of the student's lectures.

Parsing and matching are deterministic. A syllabus topic matches a lecture topic when its
words appear in that topic's title (weighted double) or slide text; the status of a
syllabus topic comes from the practice state of the lecture topics it matches.
"""

import re

MAX_ITEM = 120
MAX_LINKS = 3
MATCH_THRESHOLD = 0.5

_UNIT = re.compile(
    r"^(unit|module|chapter|part|section|week|topic)\s*[-:.#]?\s*([0-9]+|[ivxlc]+)\b[\s\-:.–—)]*(.*)$",
    re.IGNORECASE,
)
_SKIP_SECTION = re.compile(
    r"^(text\s*-?\s*books?|reference(s| books?)?|suggested readings?|course outcomes?|"
    r"learning outcomes?|outcomes?|assessment|evaluation( scheme)?|web resources|"
    r"lab(oratory)? (experiments?|exercises)|list of (experiments|practicals))\b",
    re.IGNORECASE,
)
_NOISE = re.compile(
    r"^(l\s*t\s*p(\s*c)?|credits?|total|hours?|contact hours|course code|prerequisites?|"
    r"course objectives?|objectives?|syllabus)\b",
    re.IGNORECASE,
)
_HOURS = re.compile(
    r"[\(\[]?\s*\d+\s*(hours?|hrs?|lectures?|periods?|l)\s*[\)\]]?\s*$", re.IGNORECASE
)
_BULLET = re.compile(
    r"^([\-\*•▪●◦·▸➢]|\(?\d+(\.\d+)*[.)]|\(?[a-z][.)]|\(?[ivx]+[.)])\s+", re.IGNORECASE
)
_WORD = re.compile(r"[a-z0-9]+")
_STOP = {
    "the", "and", "for", "with", "its", "their", "from", "into", "using", "use", "via",
    "introduction", "intro", "basic", "basics", "concept", "concepts", "overview",
    "types", "various", "different", "study", "applications", "application", "unit",
    "module", "chapter", "part",
}  # fmt: skip


def _clean(text):
    text = _HOURS.sub("", " ".join(text.split())).strip(" .;:,-–—")
    return _BULLET.sub("", text).strip(" .;:,-–—")


def _split(text):
    parts = [_clean(part) for part in re.split(r"[;,]", text)]
    return [part[:MAX_ITEM] for part in parts if len(part) >= 3 and not part.isdigit()]


def parse_syllabus(text):
    """[{"unit": label or None, "title": topic}] in syllabus order."""
    lines = [" ".join(line.split()) for line in (text or "").splitlines()]
    lines = [line for line in lines if line]
    has_units = any(_UNIT.match(line) for line in lines)
    items, unit, unit_name, skipping = [], None, None, False
    for line in lines:
        header = _UNIT.match(line)
        if header:
            _close_unit(items, unit, unit_name)
            skipping, unit_name = False, None
            label = f"{header[1].title()} {header[2].upper()}"
            rest = _clean(header[3])
            # "Memory Management – Paging, Segmentation": a unit name, then its topics.
            parts = re.split(r"\s+[–—-]\s+|:\s*", rest, maxsplit=1)
            name, listed = (parts[0], parts[1]) if len(parts) == 2 else (rest, "")
            if listed and ("," in listed or ";" in listed):
                unit = f"{label}: {name}" if name else label
                items += [{"unit": unit, "title": title} for title in _split(listed)]
            elif "," in rest or ";" in rest:
                unit = label
                items += [{"unit": unit, "title": title} for title in _split(rest)]
            else:
                unit = f"{label}: {rest}" if rest else label
                unit_name = rest
            continue
        if _SKIP_SECTION.match(line):
            skipping = True
            continue
        if skipping or (has_units and unit is None) or _NOISE.match(line):
            continue
        cleaned = _clean(line)
        titles = _split(cleaned) if ("," in cleaned or ";" in cleaned) else [cleaned[:MAX_ITEM]]
        items += [{"unit": unit, "title": title} for title in titles if len(title) >= 3]
    _close_unit(items, unit, unit_name)
    return items


def _close_unit(items, unit, name):
    """A named unit with no listed topics ("Module 2 - Deadlocks") is itself one topic."""
    if name and not any(item["unit"] == unit for item in items):
        items.append({"unit": unit, "title": name[:MAX_ITEM]})


def _words(text):
    words = set()
    for word in _WORD.findall((text or "").casefold()):
        if len(word) < 3 or word in _STOP:
            continue
        if word.endswith("ies") and len(word) > 4:
            word = word[:-3] + "y"
        elif word.endswith("s") and not word.endswith("ss") and len(word) > 4:
            word = word[:-1]
        words.add(word)
    return words


def match(title, topics):
    """Ids of the lecture topics a syllabus topic matches, best first.

    Each syllabus word scores 2 if it is in a topic's title, 1 if only in its slide text;
    a topic matches when it reaches half the maximum score.
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
        if score >= MATCH_THRESHOLD:
            scored.append((score, topic["id"]))
    scored.sort(key=lambda pair: -pair[0])
    return [topic_id for _, topic_id in scored[:MAX_LINKS]]


def item_status(states):
    """Status of a syllabus topic from the states of the lecture topics it matches."""
    if not states:
        return "no_notes"
    if all(state == "ready" for state in states):
        return "ready"
    if all(state == "not_started" for state in states):
        return "not_started"
    return "practising"


def summarise(statuses):
    counts = {s: statuses.count(s) for s in ("ready", "practising", "not_started", "no_notes")}
    total = len(statuses)
    return {
        **counts,
        "total": total,
        "percent_ready": round(100 * counts["ready"] / total) if total else 0,
    }
