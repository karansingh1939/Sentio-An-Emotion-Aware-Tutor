"""Real offline browser checks for the shared workspace and responsive themes."""

from pathlib import Path

import pytest
from playwright.async_api import async_playwright

from tests.browser.test_audit_e2e import UvicornServer, wait_for_server


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
            failed_requests = []
            page.on(
                "response",
                lambda response: (
                    failed_requests.append((response.status, response.url.split("/api/v1/")[-1]))
                    if response.status >= 400
                    else None
                ),
            )
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
                        "metadata": {"document_id": "all"},
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
            await page.wait_for_selector(".preview-doc-btn", state="attached")
            await page.fill("#doc-search-input", "browser-inertia")
            assert await page.locator("#doc-search-input").evaluate(
                "element => element === document.activeElement"
            )
            await page.locator(".document-row .row-menu summary").first.click()
            await page.click(".preview-doc-btn")
            await page.wait_for_selector('sentio-modal[role="dialog"]')
            assert "<script>" in await page.locator("sentio-modal").inner_text()
            assert not await page.evaluate("Boolean(window.previewInjected)")
            await page.keyboard.press("Escape")
            await page.wait_for_selector("sentio-modal", state="detached")
            assert await page.locator(".document-row .row-menu summary").first.evaluate(
                "element => element === document.activeElement"
            )
            await page.reload()
            await page.wait_for_selector(".preview-doc-btn", state="attached")
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
            from sentio.api.app import agent

            agent.sm.save_quiz(
                "browser-saved-quiz",
                login["student_id"],
                session["session_id"],
                "Saved inertia practice",
                [
                    {
                        "question_text": "Which force changes velocity?",
                        "question_type": "multiple_choice",
                        "options": ["Net force", "Color"],
                        "correct_answer": "Net force",
                        "explanation": "A net force produces acceleration.",
                        "difficulty": "beginner",
                        "topic": "Inertia",
                    }
                ],
            )
            await page.goto(url + "/#/quizzes")
            await page.wait_for_selector(".saved-quiz")
            await page.click(".saved-quiz")
            await page.check('input[name="quiz-opt"][value="B"]')
            await page.click("#submit-quiz-btn")
            await page.wait_for_selector("text=Quiz results")
            await page.goto(url + "/#/documents")
            await page.goto(url + "/#/quizzes")
            await page.wait_for_selector('#saved-practice:has-text("Your answer: Color")')
            deck = await (
                await page.request.post(
                    url + "/api/v1/flashcards/decks",
                    headers=headers,
                    data={"student_id": login["student_id"], "deck_name": "Browser review"},
                )
            ).json()
            agent.sm.save_flashcards(
                [{"front": "What is inertia?", "back": "Resistance to changes in motion."}],
                login["student_id"],
                "Inertia",
                deck["deck_id"],
            )
            await page.goto(url + "/#/flashcards")
            try:
                await page.wait_for_selector(".start-review-btn:enabled")
            except Exception as exc:
                raise AssertionError(
                    (await page.locator("#view-flashcards").inner_text(), failed_requests)
                ) from exc
            await page.click(".start-review-btn")
            await page.wait_for_selector("#edit-current-card")
            await page.click("#edit-current-card")
            await page.fill("#card-back", "A body resists changes in its velocity.")
            await page.click('sentio-modal button[type="submit"]')
            await page.wait_for_selector("sentio-modal", state="detached")
            await page.focus("#flashcard-flip-trigger")
            await page.keyboard.press("Enter")
            await page.wait_for_selector("#rating-controls-panel", state="visible")
            assert (
                "A body resists changes in its velocity."
                in await page.locator("#view-flashcards").inner_text()
            )
            await page.click('.rate-btn[data-score="4"]')
            await page.wait_for_selector("#finish-review-btn")
            await page.click("#finish-review-btn")
            await page.wait_for_selector("#show-create-deck-modal")
            cards = await (
                await page.request.get(
                    url + "/api/v1/flashcards/reviews/due?student_id=" + login["student_id"],
                    headers=headers,
                )
            ).json()
            assert cards["due_count"] == 0
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
    screenshots = Path(__file__).resolve().parents[2] / "tmp/workspace-preview"
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
            await page.wait_for_selector("#daily-budget")
            await page.fill("#daily-budget", "45")
            await page.click('#budget-form button[type="submit"]')
            await page.wait_for_selector('#plan-status:has-text("Budget saved")')
            await page.check(".plan-complete")
            await page.wait_for_selector('#plan-status:has-text("Task completion saved")')
            await page.fill("#goal-text", "Prepare for my mechanics exam")
            await page.fill("#goal-date", "2026-12-01")
            await page.click('#goal-form button[type="submit"]')
            await page.wait_for_selector(".goal-done")
            await page.reload()
            await page.wait_for_selector("#daily-budget")
            assert await page.locator("#daily-budget").input_value() == "45"
            assert await page.locator(".plan-complete").is_checked()
            assert (
                "Prepare for my mechanics exam"
                in await page.locator("#view-dashboard").inner_text()
            )
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
