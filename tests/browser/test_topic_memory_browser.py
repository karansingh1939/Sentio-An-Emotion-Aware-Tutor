"""A topic studied days ago shows as due for review, on Today and in the Library."""

import json
import uuid

import pytest
from playwright.async_api import async_playwright
from sqlalchemy import text

from tests.browser.test_audit_e2e import UvicornServer, wait_for_server
from tests.browser.test_courses_browser import PPTX
from tests.helpers import auto_answer_dialogs
from tests.integration.test_topic_mastery import QUESTIONS, _deck


@pytest.mark.browser
@pytest.mark.asyncio
async def test_a_faded_topic_can_be_practised_from_today(monkeypatch):
    from sentio.ai.providers import OllamaBackend
    from sentio.api.app import agent

    def complete(self, **kwargs):
        if "generate a quiz" in kwargs["system_prompt"].lower():
            return json.dumps({"title": "Paging", "questions": [QUESTIONS["paging"]] * 3}), 30
        return json.dumps({"text": "Paging uses frames [memory.pptx Page 1]."}), 20

    monkeypatch.setattr(OllamaBackend, "complete", complete)
    url = "http://127.0.0.1:8025"
    server = UvicornServer("sentio.api.app:app", port=8025)
    server.start()
    assert wait_for_server(url)
    try:
        async with async_playwright() as driver:
            browser = await driver.chromium.launch()
            page = await browser.new_page(viewport={"width": 1280, "height": 900})
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            await auto_answer_dialogs(page, "Operating Systems")
            await page.goto(url)
            await page.click("#auth-toggle-btn")
            email = f"memory-{uuid.uuid4().hex}@example.com"
            await page.fill("#auth-email", email)
            await page.fill("#auth-password", "StrongPassword123!")
            await page.fill("#auth-confirm-password", "StrongPassword123!")
            await page.click("#auth-submit-btn")
            await page.wait_for_selector("#auth-confirm-password", state="detached")
            await page.fill("#auth-email", email)
            await page.fill("#auth-password", "StrongPassword123!")
            await page.click("#auth-submit-btn")
            await page.wait_for_selector("#study-guide-title")
            assert await page.locator("#practise-due-btn").count() == 0

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
            await paging.locator('[data-topic-action="practise"]').click()
            await page.wait_for_selector("#generate-quiz-btn:enabled")
            await page.click("#generate-quiz-btn")
            for index in range(3):
                await page.check('input[name="quiz-opt"][value="A"]')  # "Frames": correct
                await page.click("#next-question-btn" if index < 2 else "#submit-quiz-btn")
            await page.wait_for_selector("text=Quiz results")

            await page.goto(url + "/#/documents")
            await line.filter(has_text="1 of 2 topics ready").wait_for()
            await page.click(".course-progress-panel summary")
            assert "review by" in await paging.inner_text()

            with agent.sm.persister._engine.begin() as connection:
                connection.execute(text("UPDATE quiz_attempts SET timestamp=timestamp-345600"))
            await page.goto(url + "/#/dashboard")
            await page.reload()
            card = page.locator('sentio-card[title="Topics due for review"]')
            await card.wait_for()
            assert "Paging" in await card.inner_text()
            assert "% remembered" in await card.inner_text()

            await page.goto(url + "/#/documents")
            await line.filter(has_text="0 of 2 topics ready · 1 due for review").wait_for()
            await page.click(".course-progress-panel summary")
            due = page.locator(".due-topics .topic-row")
            assert "Review due" in await due.inner_text()

            await page.goto(url + "/#/dashboard")
            await page.click("#practise-due-btn")
            await page.wait_for_selector("#generate-quiz-btn:enabled")
            assert "Practising Paging" in await page.locator("#quiz-context").inner_text()
            assert errors == [], errors
            await browser.close()
    finally:
        server.stop()
