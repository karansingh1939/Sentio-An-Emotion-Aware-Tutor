"""A student starts a batch upload, opens another screen, and comes back to find every file added.

Goldfish test F1 (2026-11-09): leaving the Library mid-upload marked every file "Not added"
although the page says "You can leave this page and return to see progress".
"""

import uuid

import pytest
from playwright.async_api import async_playwright

from tests.browser.test_audit_e2e import UvicornServer, wait_for_server


@pytest.mark.browser
@pytest.mark.asyncio
async def test_upload_batch_keeps_going_while_the_learner_is_on_another_screen():
    url = "http://127.0.0.1:8024"
    server = UvicornServer("sentio.api.app:app", port=8024)
    server.start()
    assert wait_for_server(url)
    try:
        async with async_playwright() as driver:
            browser = await driver.chromium.launch()
            page = await browser.new_page(viewport={"width": 1280, "height": 900})
            await page.goto(url)
            await page.click("#auth-toggle-btn")
            email = f"upload-away-{uuid.uuid4().hex}@example.com"
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
            files = [
                {
                    "name": f"week{n}.txt",
                    "mimeType": "text/plain",
                    "buffer": f"Week {n} notes. Mitochondria release energy {n}.".encode(),
                }
                for n in (1, 2, 3)
            ]
            await page.set_input_files("#file-uploader", files)
            await page.wait_for_selector('#upload-batch:has-text("Uploading 1 of 3")')

            # Leave straight away, as the goldfish did, then come back.
            await page.click('a[href="#/dashboard"]')
            await page.wait_for_selector("#view-dashboard", state="visible")
            await page.wait_for_timeout(1500)
            await page.go_back()
            await page.wait_for_selector("#view-documents", state="visible")

            await page.wait_for_selector(
                '#upload-batch:has-text("3 of 3 files added.")', timeout=60000
            )
            for n in (1, 2, 3):
                await page.wait_for_selector(f'.document-row:has-text("week{n}.txt")')
            assert "Not added" not in await page.locator("#upload-batch").inner_text()
            await browser.close()
    finally:
        server.stop()
