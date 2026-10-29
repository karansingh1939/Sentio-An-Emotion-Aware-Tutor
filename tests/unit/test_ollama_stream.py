import json
from types import SimpleNamespace

import pytest

from sentio.ai.providers import OllamaBackend
from sentio.ai.streaming import TutorPayload, output_schema
from sentio.jobs.control import WorkCancelled, WorkControl, execution
from sentio.shared.exceptions import InvalidModelOutput, LLMServiceUnavailableError

real_complete = OllamaBackend.complete


class Response:
    def __init__(self, lines):
        self.lines = lines
        self.closed = False

    def raise_for_status(self):
        pass

    def iter_lines(self):
        yield from self.lines

    def close(self):
        self.closed = True


def backend_with(response):
    backend = OllamaBackend()
    backend.complete = real_complete.__get__(backend)
    sent = {}

    def post(url, **kwargs):
        sent.update(kwargs)
        return response

    backend._session = SimpleNamespace(post=post)
    return backend, sent


def test_ollama_uses_schema_and_streams_only_readable_text():
    raw = json.dumps({"text": "Hello\nworld 😀", "encouragement": "yes"})
    lines = [json.dumps({"message": {"content": part}, "done": False}).encode() for part in raw]
    lines.append(json.dumps({"done": True, "eval_count": 20}).encode())
    response = Response(lines)
    backend, sent = backend_with(response)
    events = []
    with (
        execution(WorkControl(emit=lambda kind, data: events.append((kind, data)))),
        output_schema(TutorPayload),
    ):
        answer, tokens = backend.complete("prompt", [], "question")
    assert answer == raw and tokens == 20
    assert "".join(data["text"] for _, data in events) == "Hello\nworld 😀"
    assert sent["stream"] is True and sent["json"]["stream"] is True
    assert sent["json"]["format"]["properties"]["text"]["type"] == "string"
    assert response.closed


def test_disconnect_and_truncation_never_succeed():
    for lines in (
        [json.dumps({"message": {"content": '{"text":"unfinished'}}).encode()],
        [
            json.dumps(
                {
                    "message": {"content": '{"text":"valid prefix"}'},
                    "done": True,
                    "done_reason": "length",
                }
            ).encode()
        ],
    ):
        response = Response(lines)
        backend, _ = backend_with(response)
        with output_schema(TutorPayload), pytest.raises(LLMServiceUnavailableError):
            backend.complete("prompt", [], "question")
        assert response.closed


def test_completed_output_outside_the_schema_is_invalid_not_unavailable():
    raw = '{"text":123}'
    response = Response([json.dumps({"message": {"content": raw}, "done": True}).encode()])
    backend, _ = backend_with(response)
    with output_schema(TutorPayload), pytest.raises(InvalidModelOutput) as caught:
        backend.complete("prompt", [], "question")
    assert not isinstance(caught.value, LLMServiceUnavailableError)
    assert caught.value.raw == raw
    assert response.closed


def test_stream_of_small_chunks_cannot_extend_generation_deadline(monkeypatch):
    from sentio.ai import providers

    now = [0.0]
    monkeypatch.setattr(providers.time, "monotonic", lambda: now[0])

    class ExpiredResponse(Response):
        def iter_lines(self):
            now[0] = 181.0
            yield b'{"message":{"content":"{}"},"done":true}'

    response = ExpiredResponse([])
    backend, _ = backend_with(response)
    with pytest.raises(LLMServiceUnavailableError, match="time budget"):
        backend.complete("prompt", [], "question")
    assert response.closed


def test_stop_closes_upstream_response_and_releases_inference_slot():
    control = WorkControl()

    class CancelResponse(Response):
        def iter_lines(self):
            control.cancel()
            yield b'{"message":{"content":"aborted"},"done":true}'

    response = CancelResponse([])
    backend, _ = backend_with(response)
    with execution(control), pytest.raises(WorkCancelled):
        backend.complete("prompt", [], "question")
    assert response.closed
    # A subsequent independent request must acquire the same semaphore.
    backend, _ = backend_with(Response([b'{"message":{"content":"{}"},"done":true}']))
    assert backend.complete("prompt", [], "question")[0] == "{}"
