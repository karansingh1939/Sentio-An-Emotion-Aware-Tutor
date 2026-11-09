"""Learners bind a session goal and correct a saved quiz question through the visible UI."""

import json
import uuid

import pytest
from playwright.async_api import async_playwright

from tests.browser.test_audit_e2e import UvicornServer, wait_for_server


@pytest.mark.browser
@pytest.mark.asyncio
async def test_goal_selection_and_quiz_question_edit(monkeypatch):
    from sentio.ai.providers import OllamaBackend
    from sentio.api.app import agent

    def complete(**kwargs):
        if "generate a quiz" in kwargs["system_prompt"].lower():
            question = {
                "question_text": "What changes velocity?",
                "question_type": "multiple_choice",
                "options": ["Net force", "Color", "Name", "Shape"],
                "correct_answer": "Name",
                "explanation": "Generated with a wrong key.",
                "difficulty": "beginner",
                "topic": "Inertia",
            }
            return json.dumps({"title": "Inertia practice", "questions": [question] * 3}), 40
        return json.dumps({"text": "Inertia resists a change in velocity."}), 20

    monkeypatch.setattr(OllamaBackend, "complete", lambda self, **kwargs: complete(**kwargs))
    url = "http://127.0.0.1:8019"
    server = UvicornServer("sentio.api.app:app", port=8019)
    server.start()
    assert wait_for_server(url)
    try:
        async with async_playwright() as driver:
            browser = await driver.chromium.launch()
            page = await browser.new_page(viewport={"width": 1280, "height": 900})
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            await page.goto(url)
            await page.click("#auth-toggle-btn")
            email = f"goal-{uuid.uuid4().hex}@example.com"
            await page.fill("#auth-email", email)
            await page.fill("#auth-password", "StrongPassword123!")
            await page.fill("#auth-confirm-password", "StrongPassword123!")
            await page.click("#auth-submit-btn")
            await page.wait_for_selector("#auth-confirm-password", state="detached")
            await page.fill("#auth-email", email)
            await page.fill("#auth-password", "StrongPassword123!")
            await page.click("#auth-submit-btn")
            await page.wait_for_selector("#study-guide-title")
            goal_id = await page.evaluate(
                """async () => {
                    const owner = window.store.getState('currentUser').id;
                    const form = new FormData();
                    form.append('file', new File(
                        ['Inertia resists a change in velocity. A net force changes velocity.'],
                        'inertia.txt', { type: 'text/plain' },
                    ));
                    await window.sentioAPI.request('/documents/upload', { method: 'POST', body: form });
                    const goal = await window.sentioAPI.post(`/students/${owner}/goals`, {
                        goal_text: 'Pass the mechanics exam',
                    });
                    return goal.goal_id;
                }"""
            )

            await page.goto(url + "/#/tutor")
            await page.wait_for_selector(f'#f-goal option[value="{goal_id}"]', state="attached")
            await page.fill("#f-topic", "Inertia")
            await page.select_option("#f-goal", goal_id)
            await page.click("#start-btn")
            await page.wait_for_function("window.store.getState('activeSessionId')")
            session_id = await page.evaluate("window.store.getState('activeSessionId')")
            assert agent.sm.get_session(session_id).metadata["goal_id"] == goal_id

            await page.select_option("#f-goal", "")
            await page.wait_for_selector('#toast.show:has-text("Session goal cleared")')
            assert agent.sm.get_session(session_id).metadata["goal_id"] is None

            await page.locator("#session-active-bar .practise-menu summary").click()
            await page.locator("#session-active-bar").get_by_role("link", name="Try a quiz").click()
            await page.wait_for_selector("#generate-quiz-btn:enabled")
            await page.click("#generate-quiz-btn")
            await page.wait_for_selector(".practice-provenance")
            assert "Made by the local AI" in await page.locator(".practice-provenance").inner_text()

            await page.check('input[name="quiz-opt"][value="A"]')
            await page.click("#check-answer-btn")
            feedback = page.locator(".answer-feedback")
            assert "Not quite. Answer: Name" in await feedback.inner_text()
            await page.click("#edit-question-btn")
            await page.fill("#edit-question-answer", "Net force")
            await page.click('sentio-modal button[type="submit"]')
            await page.wait_for_selector("sentio-modal", state="detached")
            await page.wait_for_selector('.practice-provenance:has-text("edited by you")')
            quiz_id = await page.evaluate(
                "window.sentioAPI.get('/quizzes').then((r) => r.quizzes[0].quiz_id)"
            )
            assert agent.sm.get_quiz(quiz_id)["questions"][0]["correct_answer"] == "Net force"
            assert errors == [], errors
            await browser.close()
    finally:
        server.stop()
