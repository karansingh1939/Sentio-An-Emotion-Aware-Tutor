"""Real offline browser checks for the shared workspace and responsive themes."""

from pathlib import Path

import pytest
from playwright.async_api import async_playwright

from tests.test_audit_e2e import UvicornServer, wait_for_server


@pytest.mark.browser
@pytest.mark.asyncio
async def test_streaming_turn_is_readable_and_survives_refresh(monkeypatch):
    import json
    import threading

    from sentio.jobs.control import current_control

    release = threading.Event()

    def slow_complete(**kwargs):
        control = current_control()
        control.emit("delta", {"text": "An object remains at rest."})
        release.wait(8)
        return json.dumps({"text": "An object remains at rest."}), 10

    # Backend initialization happens during server startup.
    from sentio.ai.providers import OllamaBackend

    monkeypatch.setattr(OllamaBackend, "complete", lambda self, **kwargs: slow_complete(**kwargs))
    url = "http://127.0.0.1:8015"
    server = UvicornServer("sentio.api.app:app", port=8015)
    server.start()
    assert wait_for_server(url)
    try:
        async with async_playwright() as browser_api:
            browser = await browser_api.chromium.launch()
            page = await browser.new_page()
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            credentials = {"email": "stream-browser@example.com", "password": "StrongPassword123!"}
            assert (
                await page.request.post(url + "/api/v1/auth/register", data=credentials)
            ).status == 201
            login = await (
                await page.request.post(url + "/api/v1/auth/login", data=credentials)
            ).json()
            headers = {"Authorization": "Bearer " + login["access_token"]}
            session = await (
                await page.request.post(
                    url + "/api/v1/sessions",
                    headers=headers,
                    data={
                        "student_id": "ignored",
                        "subject": "physics",
                        "topic": "Inertia",
                        "difficulty": "beginner",
                    },
                )
            ).json()
            await page.goto(url)
            await page.evaluate(
                '([tokens, session]) => { window.store.setState("authToken", tokens.access_token); window.store.setState("refreshToken", tokens.refresh_token); window.store.setState("currentUser", {id: tokens.student_id, email: tokens.email, role: tokens.role}); window.store.setState("activeSessionId", session.session_id); }',
                [login, session],
            )
            await page.goto(url + "/#/documents")
            await page.wait_for_selector("#file-uploader", state="attached")
            await page.set_input_files(
                "#file-uploader",
                {
                    "name": "browser-inertia.txt",
                    "mimeType": "text/plain",
                    "buffer": b"Inertia means resistance to changes in motion. <script>window.previewInjected=true</script>",
                },
            )
            await page.wait_for_selector(".preview-doc-btn")
            await page.fill("#doc-search-input", "browser-inertia")
            assert await page.locator("#doc-search-input").evaluate(
                "element => element === document.activeElement"
            )
            await page.click(".preview-doc-btn")
            await page.wait_for_selector('sentio-modal[role="dialog"]')
            assert "<script>" in await page.locator("sentio-modal").inner_text()
            assert not await page.evaluate("Boolean(window.previewInjected)")
            await page.keyboard.press("Escape")
            await page.wait_for_selector("sentio-modal", state="detached")
            assert await page.locator(".preview-doc-btn").evaluate(
                "element => element === document.activeElement"
            )
            await page.reload()
            await page.wait_for_selector(".preview-doc-btn")
            await page.goto(url + "/#/tutor")
            await page.wait_for_selector("#msg-input:enabled")
            await page.fill("#msg-input", "Explain inertia")
            await page.click("#send-btn")
            await page.wait_for_selector('.msg-meta:has-text("Draft answer")')
            assert (
                await page.locator(".msg.tutor .msg-bubble").inner_text()
                == "An object remains at rest."
            )
            assert await page.locator("#stop-generation-btn").is_visible()
            release.set()
            await page.wait_for_selector("#stop-generation-btn", state="hidden")
            assert await page.locator(".msg.tutor").count() == 1
            assert "Draft" not in await page.locator(".msg.tutor").inner_text()
            await page.reload()
            await page.wait_for_selector(".msg.tutor")
            assert await page.locator(".msg.tutor").count() == 1
            state = await (
                await page.request.get(
                    url + "/api/v1/sessions/" + session["session_id"], headers=headers
                )
            ).json()
            assert state["total_exchanges"] == 1
            assert errors == [], errors
            await browser.close()
    finally:
        release.set()
        server.stop()
        server.join(timeout=10)


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
