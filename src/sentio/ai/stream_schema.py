"""Schema scope and safe incremental extraction of the tutor's JSON text field."""

import json
from contextlib import contextmanager
from contextvars import ContextVar

from pydantic import BaseModel, Field

_schema = ContextVar("sentio_output_schema", default=None)


class TutorPayload(BaseModel):
    text: str = Field(min_length=1)
    follow_up_question: str | None = None
    encouragement: str | None = None
    suggested_topic: str | None = None


def current_schema():
    return _schema.get()


@contextmanager
def output_schema(schema):
    token = _schema.set(schema)
    try:
        yield
    finally:
        _schema.reset(token)


def visible_text(raw):
    """Read only a top-level text value, including a safely terminated partial string."""
    decoder = json.JSONDecoder()
    source = raw.lstrip()
    if not source.startswith("{"):
        return ""
    index = 1
    try:
        while index < len(source):
            while index < len(source) and source[index] in " \r\n\t,":
                index += 1
            key, index = decoder.raw_decode(source, index)
            if not isinstance(key, str):
                return ""
            while index < len(source) and source[index].isspace():
                index += 1
            if source[index] != ":":
                return ""
            index += 1
            while index < len(source) and source[index].isspace():
                index += 1
            if key != "text":
                _, index = decoder.raw_decode(source, index)
                continue
            if source[index] != '"':
                return ""
            start = index
            index += 1
            safe = index
            while index < len(source):
                char = source[index]
                if char == '"':
                    return json.loads(source[start : index + 1])
                if char == "\\":
                    if index + 1 >= len(source):
                        break
                    step = 6 if source[index + 1] == "u" else 2
                    if index + step > len(source):
                        break
                    index += step
                else:
                    index += 1
                safe = index
            value = json.loads(source[start:safe] + '"')
            # Hold incomplete UTF-16 surrogate pairs until their second escape arrives.
            while value and 0xD800 <= ord(value[-1]) <= 0xDFFF:
                value = value[:-1]
            return value
    except (ValueError, IndexError):
        return ""
    return ""
