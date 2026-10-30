"""A student files several lecture decks into a course at once and studies the whole course."""

import json
import uuid
from io import BytesIO

import pytest
from playwright.async_api import async_playwright
from pptx import Presentation

from tests.browser.test_audit_e2e import UvicornServer, wait_for_server

PPTX = "application/vnd.openxmlformats-officedocument.presentationml.presentation"


def _deck(title, body):
    deck = Presentation()
    deck.slides.add_slide(deck.slide_layouts[6])
    slide = deck.slides.add_slide(deck.slide_layouts[1])
    slide.shapes.title.text = title
    slide.placeholders[1].text_frame.text = body
    buffer = BytesIO()
    deck.save(buffer)
    return buffer.getvalue()


@pytest.mark.browser
@pytest.mark.asyncio
async def test_multi_file_upload_into_a_course_then_study_it(monkeypatch):
    from sentio.ai.providers import OllamaBackend

    monkeypatch.setattr(
        OllamaBackend,
        "complete",
        lambda self, **kwargs: (
            json.dumps({"text": "Paging splits memory into frames [paging.pptx Page 2]."}),
            20,
        ),
    )
    url = "http://127.0.0.1:8021"
    server = UvicornServer("sentio.api.app:app", port=8021)
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
            email = f"courses-{uuid.uuid4().hex}@example.com"
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
                "#file-uploader",
                [
                    {
                        "name": "paging.pptx",
                        "mimeType": PPTX,
                        "buffer": _deck("Paging", "Paging splits memory into fixed size frames."),
                    },
                    {
                        "name": "broken.ppt",
                        "mimeType": "application/vnd.ms-powerpoint",
                        "buffer": b"x",
                    },
                    {
                        "name": "scheduling.txt",
                        "mimeType": "text/plain",
                        "buffer": b"Round robin gives each process a time slice.",
                    },
                ],
            )
            await page.wait_for_selector(
                '#upload-batch:has-text("2 of 3 files added. Not added: broken.ppt.")',
                timeout=60000,
            )
            group = page.locator('.course-group:has(h3:has-text("Operating Systems"))')
            assert await group.locator(".document-row").count() == 2

            await group.locator(".study-course-btn").click()
            await page.wait_for_selector("#view-tutor", state="visible")
            await page.wait_for_function("!document.getElementById('msg-input').disabled")
            await page.fill("#msg-input", "How does paging split memory?")
            await page.click("#send-btn")
            await page.locator(".msg.tutor .cite-chip.inline").first.wait_for()
            assert await page.locator(".msg.tutor .cite-chip.inline").first.inner_text() == (
                "[paging.pptx slide 2]"
            )
            chips = await page.locator(".msg.tutor .cite-chip:not(.inline)").all_inner_texts()
            assert "paging.pptx · slide 2" in chips
            assert errors == [], errors
            await browser.close()
    finally:
        server.stop()
