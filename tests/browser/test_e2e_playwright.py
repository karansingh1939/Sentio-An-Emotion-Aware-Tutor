import asyncio
import os
import time
import urllib.request
from threading import Thread

import pytest
import uvicorn
from playwright.async_api import async_playwright

from sentio.config import api_cfg

TEST_PORT = 8009
BASE_URL = f"http://127.0.0.1:{TEST_PORT}"


class UvicornServer(Thread):
    def __init__(self, app_str, host="127.0.0.1", port=8009):
        super().__init__()
        self.server = None
        self.host = host
        self.port = port
        self.app_str = app_str
        self.daemon = True

    def run(self):
        config = uvicorn.Config(self.app_str, host=self.host, port=self.port, log_level="warning")
        self.server = uvicorn.Server(config)
        self.server.run()

    def stop(self):
        if self.server:
            self.server.should_exit = True


def wait_for_server(url, timeout=45):
    start = time.time()
    while time.time() - start < timeout:
        try:
            with urllib.request.urlopen(f"{url}/") as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(0.5)
    return False


@pytest.mark.browser
@pytest.mark.asyncio
async def test_sentio_playwright_e2e():
    """Automated Playwright E2E test verifying Sentio server, UI, network, console logs, and failure capture."""
    logs_dir = os.path.join(os.getcwd(), "logs")
    os.makedirs(logs_dir, exist_ok=True)

    screenshot_path = os.path.join(logs_dir, "playwright_e2e_screenshot.png")
    snapshot_path = os.path.join(logs_dir, "playwright_e2e_snapshot.html")

    # Start FastAPI server
    server = UvicornServer("sentio.api.app:app", port=TEST_PORT)
    server.start()

    # Wait until server is healthy
    assert wait_for_server(BASE_URL, timeout=75), "FastAPI server failed to start within timeout"

    console_logs = []
    network_logs = []

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(permissions=["camera", "microphone"])
            page = await context.new_page()

            # Trap console logs
            page.on("console", lambda msg: console_logs.append(f"[{msg.type}] {msg.text}"))

            # Trap network logs
            page.on("response", lambda resp: network_logs.append(f"{resp.status} {resp.url}"))

            # 1. Navigate to Sentio main application
            response = await page.goto(BASE_URL, timeout=15000)
            assert response and response.status == 200, (
                f"Failed to load Sentio home page: {response.status if response else 'No response'}"
            )

            # 2. DOM inspection & title verification
            title = await page.title()
            assert len(title) > 0, "Page title should not be empty"

            # 3. Capture HTML snapshot and screenshot
            html_content = await page.content()
            with open(snapshot_path, "w", encoding="utf-8") as f:
                f.write(html_content)

            await page.screenshot(path=screenshot_path)

            # 4. Verify API Health Endpoint via Playwright Request Context
            health_url = f"{BASE_URL}{api_cfg.API_PREFIX}/health"
            api_resp = await page.request.get(health_url)
            assert api_resp.status == 200, f"Health endpoint failed with status {api_resp.status}"
            health_json = await api_resp.json()
            assert health_json.get("status") in ["ok", "healthy", "degraded"]

            # 5. Verify Subjects Endpoint
            subjects_url = f"{BASE_URL}{api_cfg.API_PREFIX}/subjects"
            subj_resp = await page.request.get(subjects_url)
            assert subj_resp.status == 200, (
                f"Subjects endpoint failed with status {subj_resp.status}"
            )

            await browser.close()

        print("\n[Playwright E2E Test PASS]")
        print(f"Screenshots saved to: {screenshot_path}")
        print(f"HTML snapshot saved to: {snapshot_path}")
        print(
            f"Captured {len(console_logs)} console messages & {len(network_logs)} network responses."
        )

    finally:
        server.stop()


if __name__ == "__main__":
    asyncio.run(test_sentio_playwright_e2e())
