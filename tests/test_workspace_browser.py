"""Real offline browser checks for the shared workspace and responsive themes."""

from pathlib import Path

import pytest
from playwright.async_api import async_playwright

from tests.test_audit_e2e import UvicornServer, wait_for_server


@pytest.mark.browser
@pytest.mark.asyncio
async def test_workspace_is_readable_offline_and_honest_about_failed_data():
    url = "http://127.0.0.1:8014"
    server = UvicornServer("sentio.api.app:app", port=8014)
    server.start()
    assert wait_for_server(url)
    screenshots = Path(__file__).resolve().parents[1] / "tmp/workspace-preview"
    screenshots.mkdir(parents=True, exist_ok=True)
    try:
        async with async_playwright() as browser_api:
            browser = await browser_api.chromium.launch()
            page = await browser.new_page()
            errors, external = [], []
            page.on("pageerror", lambda error: errors.append(str(error)))

            async def offline(route):
                if not route.request.url.startswith(url):
                    external.append(route.request.url)
                    await route.abort()
                else:
                    await route.continue_()

            await page.route("**/*", offline)
            await page.goto(url)
            await page.click("#auth-toggle-btn")
            await page.fill("#auth-email", "workspace@example.edu")
            await page.fill("#auth-password", "StrongPassword123!")
            await page.fill("#auth-confirm-password", "StrongPassword123!")
            await page.click("#auth-submit-btn")
            await page.wait_for_selector("#auth-confirm-password", state="detached")
            await page.fill("#auth-email", "workspace@example.edu")
            await page.fill("#auth-password", "StrongPassword123!")
            await page.click("#auth-submit-btn")
            await page.wait_for_selector("#view-auth", state="hidden")
            assert await page.locator(".nav-links .nav-link").all_text_contents() == [
                "Today",
                "Library",
                "Study",
                "Review",
                "Progress",
            ]
            assert await page.locator("html").get_attribute("data-theme") == "light"
            for theme in ("light", "dark"):
                if theme == "dark":
                    await page.click("#theme-toggle")
                for width in (390, 768, 1440):
                    await page.set_viewport_size({"width": width, "height": 900})
                    for route, view in (
                        ("dashboard", "dashboard"),
                        ("documents", "documents"),
                        ("tutor", "tutor"),
                        ("quizzes", "quizzes"),
                        ("flashcards", "flashcards"),
                        ("whiteboard", "whiteboard"),
                        ("analytics", "analytics"),
                        ("history", "history"),
                        ("settings", "settings"),
                    ):
                        await page.goto(f"{url}/#/{route}")
                        await page.wait_for_selector(f"#view-{view}", state="visible")
                        assert await page.evaluate(
                            "document.documentElement.scrollWidth <= window.innerWidth"
                        ), f"{route} overflows at {width} in {theme}"
                    await page.goto(url + "/#/dashboard")
                    await page.wait_for_selector(".today-columns")
                    await page.screenshot(path=str(screenshots / f"today-{theme}-{width}.png"))
            await page.route(
                "**/profile", lambda route: route.fulfill(status=503, json={"detail": "Offline"})
            )
            await page.goto(url + "/#/documents")
            await page.goto(url + "/#/dashboard")
            await page.wait_for_selector("#dashboard-errors", state="visible")
            assert "unavailable" in (await page.locator("#dashboard-errors").inner_text()).lower()
            assert external == [], f"Core workspace requested external assets: {external}"
            assert errors == [], errors
            await browser.close()
    finally:
        server.stop()
        server.join(timeout=10)
