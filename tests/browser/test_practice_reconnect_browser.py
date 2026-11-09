"""Cards written while the learner looks at another screen appear when they come back.

Goldfish test F10 (2026-11-09): after "Make cards", leaving and returning showed
"0 Due Cards" until a manual reload, because the screen no longer followed the job.
"""

import json
import time
import uuid

import pytest
from playwright.async_api import async_playwright

from tests.browser.test_audit_e2e import UvicornServer, wait_for_server


@pytest.mark.browser
@pytest.mark.asyncio
async def test_flashcards_made_while_away_appear_on_return(monkeypatch):
    from sentio.ai.providers import OllamaBackend

    def complete(self, **kwargs):
        if "flashcards about" in kwargs["system_prompt"].lower():
            time.sleep(4)  # a slow local model: long enough to leave and come back
            card = {"front": "What is inertia?", "back": "Resistance to changes in velocity."}
            return json.dumps({"deck_name": "Inertia", "cards": [card] * 3}), 40
        return json.dumps({"text": "Inertia resists change [mechanics.txt Page 1]."}), 20

    monkeypatch.setattr(OllamaBackend, "complete", complete)
    url = "http://127.0.0.1:8025"
    server = UvicornServer("sentio.api.app:app", port=8025)
    server.start()
    assert wait_for_server(url)
    try:
        async with async_playwright() as driver:
            browser = await driver.chromium.launch()
            page = await browser.new_page(viewport={"width": 1280, "height": 900})
            await page.goto(url)
            await page.click("#auth-toggle-btn")
            email = f"cards-away-{uuid.uuid4().hex}@example.com"
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
            await page.wait_for_function(
                "document.getElementById('file-uploader')?.disabled === false"
            )
            await page.set_input_files(
                "#file-uploader",
                {
                    "name": "mechanics.txt",
                    "mimeType": "text/plain",
                    "buffer": b"Inertia resists changes in velocity. Mass measures inertia.",
                },
            )
            await page.locator(".library-ready .study-doc-btn").click()
            await page.wait_for_selector("#view-tutor", state="visible")
            await page.wait_for_function("!document.getElementById('msg-input').disabled")

            await page.evaluate("location.hash = '#/flashcards'")
            await page.wait_for_selector("#gen-deck-select")
            await page.click("#generate-flashcards-btn")
            await page.wait_for_timeout(500)

            # Leave while the cards are still being written, then come back in the app.
            await page.evaluate("location.hash = '#/documents'")
            await page.wait_for_selector("#view-documents", state="visible")
            await page.wait_for_timeout(1000)
            await page.evaluate("location.hash = '#/flashcards'")

            # No reload: the screen reconnects and shows the new cards when ready.
            await page.wait_for_selector(".start-review-btn:enabled", timeout=30000)
            await browser.close()
    finally:
        server.stop()
