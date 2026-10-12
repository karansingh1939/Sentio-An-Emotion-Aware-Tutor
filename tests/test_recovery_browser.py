"""Real browser coverage for save-key, recovery and keyboard sign-in."""

import uuid

import pytest
from playwright.async_api import async_playwright

from tests.test_audit_e2e import UvicornServer, wait_for_server


@pytest.mark.browser
@pytest.mark.asyncio
async def test_account_recovery_from_visible_sign_in_and_settings_controls():
    url = "http://127.0.0.1:8018"
    server = UvicornServer("sentio.api.app:app", port=8018)
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
            email = f"reset-browser-{uuid.uuid4().hex}@example.com"
            await page.fill("#auth-email", email)
            await page.fill("#auth-password", "OriginalPassword123!")
            await page.fill("#auth-confirm-password", "OriginalPassword123!")
            await page.click("#auth-submit-btn")
            await page.wait_for_selector("#saved-recovery-key")
            registration_key = await page.locator("#saved-recovery-key").input_value()
            assert len(registration_key) >= 32
            async with page.expect_download() as received:
                await page.get_by_role("button", name="Download recovery key").click()
            assert (await received.value).suggested_filename == "sentio-recovery-key.txt"
            await page.fill("#auth-email", email)
            await page.fill("#auth-password", "OriginalPassword123!")
            await page.locator("#auth-password").press("Enter")
            await page.wait_for_selector("#view-auth", state="hidden")
            await page.goto(url + "/#/settings")
            await page.fill("#recovery-current-password", "IncorrectPassword123!")
            await page.click("#make-recovery-key")
            await page.wait_for_selector('#recovery-error:has-text("incorrect")')
            await page.fill("#recovery-current-password", "OriginalPassword123!")
            await page.click("#make-recovery-key")
            await page.wait_for_selector("#recovery-key-result #saved-recovery-key")
            key = await page.locator("#recovery-key-result #saved-recovery-key").input_value()
            assert key != registration_key
            await page.click("#signout-btn")
            await page.wait_for_selector("#forgot-password-btn")
            await page.click("#forgot-password-btn")
            await page.fill("#auth-email", email)
            await page.fill("#auth-recovery-key", key)
            await page.fill("#auth-password", "NewPassword123!")
            await page.fill("#auth-confirm-password", "NewPassword123!")
            await page.fill("#auth-recovery-key", "invalid-key")
            await page.click("#auth-submit-btn")
            await page.wait_for_selector('#auth-error:has-text("invalid")')
            assert await page.locator("#auth-email").input_value() == email
            await page.fill("#auth-recovery-key", key)
            await page.click("#auth-submit-btn")
            await page.wait_for_selector("#auth-recovery-key", state="detached")
            await page.wait_for_selector("#saved-recovery-key")
            replacement = await page.locator("#saved-recovery-key").input_value()
            assert replacement != key
            await page.fill("#auth-email", email)
            await page.fill("#auth-password", "NewPassword123!")
            await page.click("#auth-submit-btn")
            await page.wait_for_selector("#view-auth", state="hidden")
            assert await page.locator("#saved-recovery-key").count() == 0
            assert errors == [], errors
            await browser.close()
    finally:
        server.stop()
        server.join(timeout=15)
        assert not server.is_alive()
