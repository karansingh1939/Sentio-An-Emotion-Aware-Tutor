"""First-time learners can complete the primary path using visible controls."""

import json
import uuid
from pathlib import Path

import pytest
from playwright.async_api import async_playwright

from tests.test_audit_e2e import UvicornServer, wait_for_server


@pytest.mark.browser
@pytest.mark.asyncio
async def test_first_time_notes_to_study_to_practice_without_hidden_setup(monkeypatch):
    from sentio.ai.providers import OllamaBackend

    def complete(**kwargs):
        prompt = kwargs["system_prompt"].lower()
        if "generate a quiz" in prompt:
            question = {
                "question_text": "What changes velocity?",
                "question_type": "multiple_choice",
                "options": ["Net force", "Color", "Name", "Shape"],
                "correct_answer": "Net force",
                "explanation": "A net force changes velocity.",
                "difficulty": "beginner",
                "topic": "Inertia",
            }
            return json.dumps({"title": "Inertia practice", "questions": [question] * 3}), 40
        if "flashcards about" in prompt:
            return json.dumps(
                {
                    "deck_name": "Inertia",
                    "cards": [
                        {
                            "front": "What is inertia?",
                            "back": "Resistance to changes in velocity.",
                            "tags": ["motion"],
                        }
                    ]
                    * 3,
                }
            ), 40
        return json.dumps(
            {"text": "Inertia resists a change in velocity [mechanics.txt Page 1]."}
        ), 20

    monkeypatch.setattr(OllamaBackend, "complete", lambda self, **kwargs: complete(**kwargs))
    url = "http://127.0.0.1:8017"
    server = UvicornServer("sentio.api.app:app", port=8017)
    server.start()
    assert wait_for_server(url)
    try:
        async with async_playwright() as driver:
            browser = await driver.chromium.launch()
            page = await browser.new_page(viewport={"width": 390, "height": 844})
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            await page.goto(url)
            await page.click("#auth-toggle-btn")
            email = f"beginner-{uuid.uuid4().hex}@example.com"
            await page.fill("#auth-email", email)
            await page.fill("#auth-password", "StrongPassword123!")
            await page.fill("#auth-confirm-password", "StrongPassword123!")
            await page.click("#auth-submit-btn")
            await page.wait_for_selector("#auth-confirm-password", state="detached")
            await page.fill("#auth-email", email)
            await page.fill("#auth-password", "StrongPassword123!")
            await page.click("#auth-submit-btn")
            await page.wait_for_selector("#study-guide-title")
            await page.get_by_role("link", name="Add your first notes", exact=True).click()
            await page.wait_for_selector("#file-uploader", state="attached")
            await page.set_input_files(
                "#file-uploader",
                {
                    "name": "mechanics.txt",
                    "mimeType": "text/plain",
                    "buffer": b"Inertia resists changes in velocity. A net force changes velocity. Mass measures inertia.",
                },
            )
            await page.wait_for_selector(".library-ready .study-doc-btn")
            assert "Ready to study" in await page.locator(".document-row").inner_text()
            await page.locator(".library-ready .study-doc-btn").click()
            await page.wait_for_selector("#new-sess-topic")
            await page.select_option("#new-sess-subject", "physics")
            await page.fill("#new-sess-topic", "Inertia")
            assert await page.locator("#new-sess-grounding").is_disabled()
            selected = await page.locator("#new-sess-grounding").input_value()
            await page.click("#new-sess-submit-btn")
            await page.wait_for_selector("sentio-modal", state="detached")
            await page.wait_for_selector("#view-tutor", state="visible")
            await page.wait_for_function("!document.getElementById('msg-input').disabled")
            await page.wait_for_function(
                "value => document.getElementById('f-grounding').value === value", arg=selected
            )
            await page.fill("#msg-input", "What is inertia?")
            await page.click("#send-btn")
            await page.wait_for_selector(".msg.tutor")
            assert "mechanics.txt" in await page.locator(".msg.tutor").inner_text()
            await page.locator("#session-active-bar").get_by_role("link", name="Try a quiz").click()
            await page.wait_for_selector("#generate-quiz-btn:enabled")
            assert not await page.locator("#quiz-topic").is_visible()
            await page.click("#generate-quiz-btn")
            for index in range(3):
                await page.check('input[name="quiz-opt"][value="A"]')
                await page.click("#next-question-btn" if index < 2 else "#submit-quiz-btn")
            await page.wait_for_selector("text=Assessment Results")
            await page.goto(url + "/#/tutor")
            await (
                page.locator("#session-active-bar")
                .get_by_role("link", name="Make flashcards")
                .click()
            )
            await page.wait_for_selector("#show-create-deck-modal")
            await page.wait_for_selector("#gen-deck-select")
            await page.click("#generate-flashcards-btn")
            await page.wait_for_selector(".start-review-btn:enabled")
            await page.click(".start-review-btn")
            await page.click("#flashcard-flip-trigger")
            await page.wait_for_selector("#rating-controls-panel", state="visible")
            assert not await page.locator(".flashcard-front").is_visible()
            assert await page.locator(".flashcard-back").is_visible()
            assert await page.get_by_role("button", name="Again", exact=True).is_visible()
            assert "Resistance to changes" in await page.locator("#view-flashcards").inner_text()
            assert errors == [], errors
            assert await page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
            images = Path(__file__).resolve().parents[1] / "tmp/workspace-preview"
            images.mkdir(parents=True, exist_ok=True)
            await page.screenshot(path=str(images / "beginner-review-mobile.png"))
            writes = []

            async def lose_rating_response(route):
                writes.append(1)
                response = await route.fetch()
                assert response.status == 200
                await route.abort()

            await page.route("**/flashcards/*/review", lose_rating_response)
            await page.click('.rate-btn[data-score="4"]')
            await page.wait_for_selector('sentio-toast:has-text("Review failed")')
            await page.click('.rate-btn[data-score="4"]')
            await page.wait_for_selector('.view-header:has-text("Card 2 of 3")')
            assert len(writes) == 1, (
                "A lost response must confirm the saved rating without another write"
            )
            await browser.close()
    finally:
        server.stop()
        server.join(timeout=15)
        assert not server.is_alive()
