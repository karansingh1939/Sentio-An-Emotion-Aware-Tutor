"""The real camera path on the slides page, with Chromium's synthetic camera (no webcam).

Needs the optional MediaPipe assets (see docs/guides/EMOTION.md); skipped without them.
"""

import asyncio
from pathlib import Path

import pytest
from playwright.async_api import async_playwright

from tests.browser.test_audit_e2e import UvicornServer, wait_for_server
from tests.browser.test_slide_study_browser import (
    _consent_for,
    _fake_model,
    _sign_in_and_open_slides,
)
from tests.helpers import auto_answer_dialogs

VENDOR = Path(__file__).resolve().parents[2] / "src/sentio/static/vendor/mediapipe"
pytestmark = pytest.mark.skipif(
    not (VENDOR / "vision_bundle.mjs").exists(), reason="MediaPipe assets are not installed"
)


@pytest.mark.browser
@pytest.mark.asyncio
async def test_the_camera_runs_on_the_slides_page_and_stops_when_leaving(monkeypatch):
    from sentio.config import emotion_cfg

    _fake_model(monkeypatch, [])
    monkeypatch.setattr(emotion_cfg, "ENABLED", True)
    url = "http://127.0.0.1:8028"
    server = UvicornServer("sentio.api.app:app", port=8028)
    server.start()
    assert wait_for_server(url)
    try:
        async with async_playwright() as driver:
            browser = await driver.chromium.launch(
                args=["--use-fake-device-for-media-stream", "--use-fake-ui-for-media-stream"]
            )
            context = await browser.new_context(viewport={"width": 1280, "height": 900})
            await context.grant_permissions(["camera"])
            page = await context.new_page()
            errors, frames = [], []
            page.on("pageerror", lambda error: errors.append(str(error)))
            await auto_answer_dialogs(page, "Operating Systems")
            page.on(
                "websocket",
                lambda ws: ws.on("framesent", lambda payload: frames.append(len(payload))),
            )
            email = await _sign_in_and_open_slides(page, url)
            _consent_for(email)
            await page.click("#slide-camera-toggle")
            await page.get_by_role("button", name="Allow camera").click()

            # The synthetic camera shows no face, so the learner reads as looking away.
            mood = page.locator("#slide-mood").filter(has_text="looking away")
            await mood.wait_for(timeout=60000)
            assert await page.evaluate("!document.getElementById('cam-video').paused")
            # The access token, then live frames: a paused video would repeat one picture.
            assert len(frames) >= 3 and len(set(frames[1:])) > 1, frames

            await page.goto(url + "/#/documents")
            await asyncio.sleep(1)
            assert not await page.evaluate("Boolean(window.camStream)")
            live = await page.evaluate(
                "Array.from(document.querySelectorAll('video')).flatMap(v => v.srcObject ?"
                " v.srcObject.getTracks() : []).filter(t => t.readyState === 'live').length"
            )
            assert live == 0
            assert errors == [], errors
            await browser.close()
    finally:
        server.stop()
        server.join(timeout=10)
