"""A student studies a lecture slide by slide; the optional camera mood only changes tone.

Written against docs/project/phase-4-slide-study.md. The real camera toggle is never clicked
(MediaPipe assets are absent in tests): camera readings are recorded server-side instead.
"""

import asyncio
import json
import time
import uuid

import pytest
from playwright.async_api import async_playwright

from tests.browser.test_audit_e2e import UvicornServer, wait_for_server
from tests.browser.test_courses_browser import PPTX
from tests.integration.test_topic_mastery import _deck

SIMPLER = "Explain this slide more simply."


def _fake_model(monkeypatch, messages):
    """Answer by citing the first passage the page sent, and keep every question asked."""
    from sentio.ai.providers import OllamaBackend

    def complete(self, **kwargs):
        try:
            data = json.loads(kwargs["user_message"])
        except ValueError:
            data = {}
        messages.append(data.get("student_question", kwargs["user_message"]))
        passages = data.get("source_passages") or []
        cite = passages[0]["reference"] if passages else ""
        return json.dumps({"text": f"This slide is about paging {cite}."}), 20

    monkeypatch.setattr(OllamaBackend, "complete", complete)


async def _sign_in_and_open_slides(page, url):
    await page.goto(url)
    await page.click("#auth-toggle-btn")
    email = f"slides-{uuid.uuid4().hex}@example.com"
    await page.fill("#auth-email", email)
    await page.fill("#auth-password", "StrongPassword123!")
    await page.fill("#auth-confirm-password", "StrongPassword123!")
    await page.click("#auth-submit-btn")
    await page.wait_for_selector("#auth-confirm-password", state="detached")
    await page.fill("#auth-email", email)
    await page.fill("#auth-password", "StrongPassword123!")
    await page.click("#auth-submit-btn")
    await page.wait_for_selector("#study-guide-title")

    await page.goto(url + "/#/documents")
    await page.wait_for_selector("#upload-course")
    await page.select_option("#upload-course", "__new__")
    await page.wait_for_selector(
        '#upload-course option[selected]:has-text("Operating Systems")', state="attached"
    )
    await page.set_input_files(
        "#file-uploader", {"name": "memory.pptx", "mimeType": PPTX, "buffer": _deck()}
    )
    await (
        page.locator(".course-progress")
        .filter(has_text="0 of 2 topics ready")
        .wait_for(timeout=60000)
    )
    await page.locator('[data-action="study-slides"]').first.click()
    await page.wait_for_selector("#slides-view")
    await page.locator(".slide-item").nth(2).wait_for()
    return email


async def _wait_for_question(messages, question, timeout=20):
    """The fake model records each question it is asked; wait until the page has sent this one."""
    deadline = time.monotonic() + timeout
    while question not in messages:
        assert time.monotonic() < deadline, f"The page never asked {question!r}: {messages}"
        await asyncio.sleep(0.2)


async def _explain_and_read(page):
    await page.click("#slide-explain")
    answer = page.locator("#slide-answer")
    await page.wait_for_function(
        "() => document.getElementById('slide-answer').innerText.trim().length > 0"
    )
    return answer


def _slides_session():
    """ASSUMPTION: the page creates the session with metadata {"document_id", "mode": "slides"}
    (the contract's way to start slide study), so it can be found in-process by its mode."""
    from sentio.api.app import agent

    found = [
        session
        for session in agent.sm._sessions.values()
        if session.metadata.get("mode") == "slides"
    ]
    return found[-1] if found else None


def _consent_for(email, allowed=True):
    from sentio.api.app import agent
    from sentio.auth.models import ConsentHistory

    owner = agent.sm.persister.auth_repo.get_account_by_email(email).student_id
    agent.sm.persister.auth_repo.save_consent(
        ConsentHistory(
            student_id=owner,
            consent_version="camera-v1",
            preferences_json=json.dumps({"telemetry": allowed}),
            timestamp=time.time(),
        )
    )


async def _keep_struggling(session, stop):
    """Camera confusion, read once a second for a while before and all through the test."""
    from sentio.session.models import EmotionEvent

    now = time.time()
    for offset in range(25, 0, -1):
        session.emotion_timeline.record(EmotionEvent(now - offset, "sad", "struggling", 0.9, "x"))
    while not stop.is_set():
        session.emotion_timeline.record(
            EmotionEvent(time.time(), "sad", "struggling", 0.9, "simplify")
        )
        await asyncio.sleep(1)


@pytest.mark.browser
@pytest.mark.asyncio
async def test_study_slides_one_by_one_and_accept_a_simpler_explanation(monkeypatch):
    from sentio.config import emotion_cfg

    messages = []
    _fake_model(monkeypatch, messages)
    monkeypatch.setattr(emotion_cfg, "ENABLED", True)
    url = "http://127.0.0.1:8026"
    server = UvicornServer("sentio.api.app:app", port=8026)
    server.start()
    assert wait_for_server(url)
    stop = asyncio.Event()
    mood_task = None
    try:
        async with async_playwright() as driver:
            browser = await driver.chromium.launch()
            page = await browser.new_page(viewport={"width": 1280, "height": 900})
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.on("dialog", lambda dialog: dialog.accept("Operating Systems"))
            email = await _sign_in_and_open_slides(page, url)

            assert await page.locator(".slide-item").count() == 3
            first = await page.locator("#slide-title").inner_text()
            assert first.strip()
            await page.click("#slide-next")
            await page.wait_for_function(
                "first => document.getElementById('slide-title').innerText !== first", arg=first
            )
            second = await page.locator("#slide-title").inner_text()
            await page.click("#slide-prev")
            await page.wait_for_function(
                "first => document.getElementById('slide-title').innerText === first", arg=first
            )
            await page.click("#slide-next")
            await page.wait_for_function(
                "second => document.getElementById('slide-title').innerText === second", arg=second
            )

            answer = await _explain_and_read(page)
            await page.wait_for_function(
                "() => /slide 2/i.test(document.getElementById('slide-answer').innerText)"
            )
            assert "paging" in (await answer.inner_text()).lower()
            assert messages[-1] == "Explain this slide."

            # Mood shows only while the camera runs. A real one needs a webcam and MediaPipe, so a
            # trackless stream stands in for it; the readings are recorded server-side below.
            _consent_for(email)
            await page.evaluate("window.camStream = new MediaStream()")
            session = _slides_session()
            assert session is not None
            mood_task = asyncio.create_task(_keep_struggling(session, stop))
            await page.locator("#slide-mood").filter(has_text="unsure").wait_for(timeout=45000)
            chip = page.locator("#slide-mood")
            labelled = (await chip.inner_text()) + (await chip.get_attribute("title") or "")
            assert "guess" in labelled.lower(), "the chip must say it is only a guess"
            await page.locator("#slide-nudge").wait_for(timeout=45000)
            await page.click("#slide-nudge-accept")
            await _wait_for_question(messages, SIMPLER)
            await page.wait_for_function(
                "() => /slide 2/i.test(document.getElementById('slide-answer').innerText)"
            )
            assert errors == [], errors
            await browser.close()
    finally:
        stop.set()
        if mood_task:
            await mood_task
        server.stop()
        server.join(timeout=10)  # frees port 8026 for the next test in this file


@pytest.mark.browser
@pytest.mark.asyncio
async def test_slides_work_and_the_camera_switch_is_hidden_when_the_feature_is_off(monkeypatch):
    from sentio.config import emotion_cfg

    messages = []
    _fake_model(monkeypatch, messages)
    monkeypatch.setattr(emotion_cfg, "ENABLED", False)
    url = "http://127.0.0.1:8026"
    server = UvicornServer("sentio.api.app:app", port=8026)
    server.start()
    assert wait_for_server(url)
    try:
        async with async_playwright() as driver:
            browser = await driver.chromium.launch()
            page = await browser.new_page(viewport={"width": 1280, "height": 900})
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.on("dialog", lambda dialog: dialog.accept("Operating Systems"))
            await _sign_in_and_open_slides(page, url)

            assert not await page.locator("#slide-camera-toggle").is_visible()
            assert not await page.locator("#slide-mood").is_visible()
            assert not await page.locator("#slide-nudge").is_visible()

            await page.click("#slide-next")
            await _explain_and_read(page)
            await page.wait_for_function(
                "() => /slide 2/i.test(document.getElementById('slide-answer').innerText)"
            )
            await page.fill("#slide-question", "What is a page table?")
            await page.click("#slide-ask")
            await _wait_for_question(messages, "What is a page table?")
            assert not await page.locator("#slide-camera-toggle").is_visible()
            assert errors == [], errors
            await browser.close()
    finally:
        server.stop()
        server.join(timeout=10)  # frees port 8026 for the next test in this file
