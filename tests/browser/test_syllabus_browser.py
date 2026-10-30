"""A student adds a course syllabus, sees what their notes don't cover, and fixes a match."""

import uuid
from pathlib import Path

import pytest
from playwright.async_api import async_playwright

from tests.browser.test_audit_e2e import UvicornServer, wait_for_server
from tests.browser.test_courses_browser import PPTX
from tests.integration.test_syllabus_progress import SYLLABUS
from tests.integration.test_topic_mastery import _deck


@pytest.mark.browser
@pytest.mark.asyncio
async def test_add_a_syllabus_and_correct_a_match():
    url = "http://127.0.0.1:8023"
    server = UvicornServer("sentio.api.app:app", port=8023)
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
            email = f"syllabus-{uuid.uuid4().hex}@example.com"
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
                .filter(has_text="topics ready")
                .wait_for(timeout=60000)
            )
            await page.click(".course-progress-panel summary")
            await page.fill(".syllabus-text", SYLLABUS)
            await page.click('[data-syllabus-action="save"]')
            await (
                page.locator(".course-progress")
                .filter(has_text="0% of the syllabus ready")
                .wait_for()
            )
            await page.click(".course-progress-panel summary")
            virtual = page.locator('.syllabus-item:has-text("Virtual memory")')
            assert "Not in your notes yet" in await virtual.inner_text()
            paging = page.locator('.syllabus-item:has-text("Paging")').first
            assert "memory.pptx · Paging (slides 1–2)" in await paging.inner_text()
            images = Path(__file__).resolve().parents[2] / "tmp/workspace-preview"
            images.mkdir(parents=True, exist_ok=True)
            await page.locator(".syllabus").screenshot(path=str(images / "syllabus.png"))

            option = await virtual.locator("select option", has_text="Paging").get_attribute(
                "value"
            )
            await virtual.locator("select").select_option(option)
            await page.click(".course-progress-panel summary")
            virtual = page.locator('.syllabus-item:has-text("Virtual memory")')
            await virtual.filter(has_text="Not started").wait_for()
            assert errors == [], errors
            await browser.close()
    finally:
        server.stop()
