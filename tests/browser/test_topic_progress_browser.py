"""A student practises a topic from the Library and sees it become a weak topic to revisit."""

import json
import uuid
from pathlib import Path

import pytest
from playwright.async_api import async_playwright

from tests.browser.test_audit_e2e import UvicornServer, wait_for_server
from tests.browser.test_courses_browser import PPTX
from tests.integration.test_topic_mastery import QUESTIONS, _deck


@pytest.mark.browser
@pytest.mark.asyncio
async def test_practise_a_topic_and_find_it_among_weak_topics(monkeypatch):
    from sentio.ai.providers import OllamaBackend

    def complete(self, **kwargs):
        if "generate a quiz" in kwargs["system_prompt"].lower():
            return json.dumps({"title": "Paging", "questions": [QUESTIONS["paging"]] * 3}), 30
        return json.dumps({"text": "Paging uses frames [memory.pptx Page 1]."}), 20

    monkeypatch.setattr(OllamaBackend, "complete", complete)
    url = "http://127.0.0.1:8022"
    server = UvicornServer("sentio.api.app:app", port=8022)
    server.start()
    assert wait_for_server(url)
    try:
        async with async_playwright() as driver:
            browser = await driver.chromium.launch()
            page = await browser.new_page(viewport={"width": 1280, "height": 900})
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.on("dialog", lambda dialog: dialog.accept("Operating Systems"))
            await page.goto(url)
            await page.click("#auth-toggle-btn")
            email = f"topics-{uuid.uuid4().hex}@example.com"
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
            line = page.locator(".course-progress")
            await line.filter(has_text="0 of 2 topics ready").wait_for(timeout=60000)
            await page.click(".course-progress-panel summary")
            paging = page.locator('.course-progress-body .topic-row:has-text("Paging")')
            assert "slides 1–2" in await paging.inner_text()
            assert "Not started" in await paging.inner_text()

            await paging.locator('[data-topic-action="practise"]').click()
            await page.wait_for_selector("#generate-quiz-btn:enabled")
            assert "Practising Paging" in await page.locator("#quiz-context").inner_text()
            await page.click("#generate-quiz-btn")
            for index in range(3):
                await page.check('input[name="quiz-opt"][value="B"]')  # "Threads": wrong
                await page.click("#next-question-btn" if index < 2 else "#submit-quiz-btn")
            await page.wait_for_selector("text=Assessment Results")

            await page.goto(url + "/#/documents")
            await line.filter(has_text="0 of 2 topics ready · 1 practising").wait_for()
            await page.click(".course-progress-panel summary")
            weak = page.locator(".weak-topics .topic-row")
            assert await weak.count() == 1
            images = Path(__file__).resolve().parents[2] / "tmp/workspace-preview"
            images.mkdir(parents=True, exist_ok=True)
            await page.locator(".course-group").first.screenshot(
                path=str(images / "topic-progress.png")
            )
            assert "0 of 3 correct recently" in await weak.inner_text()
            await page.click(".practise-weak-btn")
            await page.wait_for_selector("#generate-quiz-btn:enabled")
            assert "Practising Paging" in await page.locator("#quiz-context").inner_text()
            assert errors == [], errors
            await browser.close()
    finally:
        server.stop()
