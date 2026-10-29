"""Capture screenshots of the main study screens with a deterministic stand-in model.

Runs Sentio in-process on a disposable home and walks the normal journey in Chromium:
sign up, upload notes, ask a question, take a quiz and review flashcards. Answers come
from a fixed fake provider, so the images show the interface, not model quality.

    uv run python scripts/dev/screenshots.py --output docs/images
"""

import argparse
import asyncio
import json
import os
import sys
import tempfile
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NOTES = (
    b"Newton's first law: an object stays at rest or moves at constant velocity unless a "
    b"net external force acts on it. Inertia is resistance to a change in velocity. Mass "
    b"measures inertia. A net force causes acceleration."
)


ANSWER = json.dumps(
    {
        "text": (
            "Inertia is an object's resistance to a change in its velocity. By Newton's first "
            "law, a body stays at rest or keeps moving at constant velocity until a net external "
            "force acts on it, and its mass measures how much inertia it has "
            "[mechanics-notes.txt Page 1]."
        ),
        "follow_up_question": "What would change the velocity of a puck sliding on ice?",
    }
)


def configure(home):
    os.environ.update(
        {
            "SENTIO_HOME": str(home),
            "QDRANT_MODE": "memory",
            "HF_HUB_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
            "ENV": "development",
        }
    )
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / "src"))
    from tests.helpers import complete

    from sentio.ai.providers import OllamaBackend

    def fake(self, system_prompt, history, user_message, **kwargs):
        if system_prompt.startswith("You are a patient study tutor."):
            return ANSWER, 40
        return complete(system_prompt, history, user_message, **kwargs)

    OllamaBackend.load = lambda self: None
    OllamaBackend.complete = fake


async def capture(url, output, widths, themes):
    from playwright.async_api import async_playwright

    async with async_playwright() as driver:
        browser = await driver.chromium.launch()
        page = await browser.new_page(viewport={"width": 1280, "height": 860})
        await page.goto(url)
        await page.wait_for_selector("#auth-toggle-btn")
        shots = [("sign-in", None)]

        email = f"demo-{uuid.uuid4().hex[:8]}@example.com"
        await page.click("#auth-toggle-btn")
        await page.fill("#auth-email", email)
        await page.fill("#auth-password", "StrongPassword123!")
        await page.fill("#auth-confirm-password", "StrongPassword123!")
        await page.click("#auth-submit-btn")
        await page.wait_for_selector("#auth-confirm-password", state="detached")
        await page.fill("#auth-email", email)
        await page.fill("#auth-password", "StrongPassword123!")
        await page.click("#auth-submit-btn")
        await page.wait_for_selector("#study-guide-title")
        await page.evaluate(
            """async () => {
                const owner = window.store.getState('currentUser').id;
                await window.sentioAPI.post(`/students/${owner}/goals`, {
                    goal_text: 'Prepare for the mechanics exam',
                });
            }"""
        )

        await page.goto(url + "/#/documents")
        await page.wait_for_selector("#file-uploader", state="attached")
        await page.set_input_files(
            "#file-uploader",
            {"name": "mechanics-notes.txt", "mimeType": "text/plain", "buffer": NOTES},
        )
        await page.wait_for_selector(".library-ready .study-doc-btn", timeout=60000)
        await page.locator(".library-ready .study-doc-btn").click()
        await page.wait_for_selector("#new-sess-topic")
        await page.fill("#new-sess-topic", "Newton's first law")
        await page.click("#new-sess-submit-btn")
        await page.wait_for_selector("sentio-modal", state="detached")
        await page.wait_for_function("!document.getElementById('msg-input').disabled")
        await page.fill("#msg-input", "What is inertia?")
        await page.click("#send-btn")
        await page.wait_for_selector(".msg.tutor", timeout=60000)
        shots.append(("study", "#/tutor"))

        await page.locator("#session-active-bar").get_by_role("link", name="Try a quiz").click()
        await page.wait_for_selector("#generate-quiz-btn:enabled")
        await page.click("#generate-quiz-btn")
        await page.wait_for_selector("#edit-question-btn", timeout=60000)
        shots.append(("quiz", None))

        await page.goto(url + "/#/tutor")
        await (
            page.locator("#session-active-bar").get_by_role("link", name="Make flashcards").click()
        )
        await page.wait_for_selector("#generate-flashcards-btn")
        await page.click("#generate-flashcards-btn")
        await page.wait_for_selector(".start-review-btn:enabled", timeout=60000)
        await page.click(".start-review-btn")
        await page.click("#flashcard-flip-trigger")
        shots.append(("flashcards", None))
        for name, route in [
            ("today", "#/dashboard"),
            ("library", "#/documents"),
            ("progress", "#/analytics"),
            ("settings", "#/settings"),
        ]:
            shots.append((name, route))

        output.mkdir(parents=True, exist_ok=True)
        for theme in themes:
            await page.evaluate("theme => window.store.setState('theme', theme)", theme)
            for width in widths:
                await page.set_viewport_size({"width": width, "height": 860})
                for name, route in shots:
                    if name == "sign-in":
                        continue
                    if route:
                        await page.goto(url + "/" + route)
                        await page.wait_for_timeout(700)
                    elif name == "quiz":
                        await page.goto(url + "/#/quizzes")
                        await page.wait_for_selector(".saved-quiz", timeout=10000)
                        await page.locator(".saved-quiz").first.click()
                        await page.wait_for_selector("#edit-question-btn")
                    elif name == "flashcards":
                        await page.goto(url + "/#/flashcards")
                        await page.wait_for_selector(".start-review-btn:enabled")
                        await page.click(".start-review-btn")
                        await page.click("#flashcard-flip-trigger")
                    await page.evaluate(
                        "document.querySelectorAll('sentio-toast').forEach((t) => t.remove())"
                    )
                    await page.screenshot(path=str(output / f"{name}-{theme}-{width}.png"))
        await page.evaluate("window.store.setState('authToken', null)")
        await browser.close()


def make_gif(folder, target):
    from PIL import Image

    names = ["today", "library", "study", "quiz", "flashcards", "progress"]
    frames = [
        Image.open(folder / f"{name}-light-1280.png").convert("RGB").resize((960, 645))
        for name in names
        if (folder / f"{name}-light-1280.png").exists()
    ]
    target.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(target, save_all=True, append_images=frames[1:], duration=1600, loop=0)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", type=Path, default=ROOT / "tmp/screenshots")
    parser.add_argument("--widths", type=int, nargs="+", default=[1280, 390])
    parser.add_argument("--themes", nargs="+", default=["light", "dark"])
    parser.add_argument("--port", type=int, default=8031)
    parser.add_argument("--gif", type=Path, help="Also write a journey GIF (light, 1280px)")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(
        prefix="sentio-shots-", dir=ROOT / "tmp", ignore_cleanup_errors=True
    ) as home:
        (Path(home) / "data").mkdir()
        configure(home)
        from tests.browser.test_audit_e2e import UvicornServer, wait_for_server

        url = f"http://127.0.0.1:{args.port}"
        server = UvicornServer("sentio.api.app:app", port=args.port)
        server.start()
        if not wait_for_server(url):
            raise SystemExit("Sentio did not start")
        try:
            asyncio.run(capture(url, args.output, args.widths, args.themes))
        finally:
            server.stop()
    if args.gif:
        make_gif(args.output, args.gif)
    print(f"Screenshots written to {args.output}")


if __name__ == "__main__":
    main()
