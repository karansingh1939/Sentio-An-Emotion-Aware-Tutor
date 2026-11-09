import os
import time
import urllib.request
from pathlib import Path
from threading import Thread

import pytest
import uvicorn
from fastapi.testclient import TestClient
from playwright.async_api import async_playwright

from sentio.api.app import PREFIX, app
from sentio.config import api_cfg, nlp_cfg

TEST_PORT = 8011
BASE_URL = f"http://127.0.0.1:{TEST_PORT}"


class UvicornServer(Thread):
    def __init__(self, app_str, host="127.0.0.1", port=TEST_PORT):
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
        # Wait for the app's shutdown to finish. All test servers share one app, so a
        # shutdown that ends late stops the next test's job worker (seen on Linux CI:
        # uploads were accepted but never processed).
        if self.is_alive():
            self.join(timeout=30)


def wait_for_server(url, timeout=30):
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
async def test_sentio_real_browser_e2e_and_tenant_isolation():
    """Execute real browser workflows for registration, document library, session grounding, mid-session switching, resume validation, and tenant isolation."""
    # Ensure test files directory exists
    os.makedirs("data/test_uploads", exist_ok=True)
    file_a_path = os.path.abspath("data/test_uploads/kinematics_test.txt")
    file_b_path = os.path.abspath("data/test_uploads/thermodynamics_test.txt")

    with open(file_a_path, "w", encoding="utf-8") as f:
        f.write(
            "Kinematics is the study of motion of objects without reference to the forces that cause motion. Velocity is displacement over time."
        )

    with open(file_b_path, "w", encoding="utf-8") as f:
        f.write(
            "Thermodynamics is the study of heat, work, entropy, and the laws governing their conversion. Entropy always increases in a closed system."
        )

    # Start FastAPI server
    api_cfg.ENFORCE_AUTH = True
    nlp_cfg.QDRANT_MODE = "memory"
    server = UvicornServer("sentio.api.app:app", port=TEST_PORT)
    server.start()

    assert wait_for_server(BASE_URL, timeout=45), "Server failed to launch"

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(permissions=["camera"])
            page = await context.new_page()
            failed_requests = []
            page.on(
                "response",
                lambda response: (
                    failed_requests.append((response.status, response.url.split("/api/v1/")[-1]))
                    if response.status >= 400
                    else None
                ),
            )

            # Enable logging of browser console messages and network traffic
            page.on("console", lambda msg: print(f"[BROWSER CONSOLE] {msg.type}: {msg.text}"))
            page.on("request", lambda req: print(f"[BROWSER REQUEST] {req.method} {req.url}"))
            page.on("response", lambda resp: print(f"[BROWSER RESPONSE] {resp.status} {resp.url}"))

            timestamp = int(time.time() * 1000)
            email_a = f"usera_{timestamp}@sentio.edu"
            password = "StrongPassword123!"

            # ----------------------------------------------------
            # PHASE 3: USER A REGISTER & LOGIN
            # ----------------------------------------------------
            await page.goto(BASE_URL)

            # Click Create Account
            await page.click("#auth-toggle-btn")
            await page.fill("#auth-email", email_a)
            await page.fill("#auth-password", password)
            await page.fill("#auth-confirm-password", password)
            await page.click("#auth-submit-btn")

            # Wait for confirm password to disappear (indicating transition back to login view)
            await page.wait_for_selector("#auth-confirm-password", state="detached")

            # Click Sign In, type details and sign in
            await page.fill("#auth-email", email_a)
            await page.fill("#auth-password", password)
            await page.click("#auth-submit-btn")

            # Verify transitioned to dashboard
            try:
                await page.wait_for_selector("#sidebar", timeout=10000)
            except Exception as e:
                # Dump diagnostic DOM structures to stdout
                sidebar_html = await page.eval_on_selector("#sidebar", "el => el.outerHTML")
                auth_html = await page.eval_on_selector("#view-auth", "el => el.outerHTML")
                app_html = await page.eval_on_selector("#app", "el => el.outerHTML")
                print(f"\n[DIAGNOSTIC] wait_for_selector failed: {e}")
                print(f"[DIAGNOSTIC] #sidebar HTML: {sidebar_html}")
                print(f"[DIAGNOSTIC] #view-auth HTML: {auth_html}")
                print(f"[DIAGNOSTIC] #app HTML: {app_html}")
                raise e

            # Navigate to Documents View
            await page.click('a[href="#/documents"]')
            await page.wait_for_selector("#file-uploader", state="attached")
            await page.wait_for_selector("#view-documents #drop-zone", state="visible")
            await page.wait_for_function(
                "document.getElementById('file-uploader')?.disabled === false"
            )

            # Upload Document A
            async with page.expect_response(
                lambda reply: (
                    reply.url.endswith("/documents/jobs") and reply.request.method == "POST"
                )
            ) as submission:
                await page.set_input_files("#file-uploader", file_a_path)
            first_upload = await (await submission.value).json()

            # Wait for list update and confirm document appears in table
            await page.wait_for_selector("text=kinematics_test.txt", timeout=20000)

            # Navigate to Tutor View
            await page.click('a[href="#/tutor"]')
            await page.wait_for_selector("#start-btn")
            await page.fill("#f-topic", "kinematics")
            await page.wait_for_selector(
                '#f-grounding option:has-text("kinematics_test.txt")', state="attached"
            )
            val_a = await page.evaluate(
                """() => [...document.querySelector('#f-grounding').options].find(o => o.text.includes('kinematics_test.txt')).value"""
            )
            await page.select_option("#f-grounding", value=val_a)
            await page.click("#start-btn")

            # Wait for session start
            await page.wait_for_timeout(2000)

            # Verify tutor connection label says live
            conn_label = await page.inner_text("#conn-label")
            assert "Session active" in conn_label, "Session failed to start"

            # Send chat question
            await page.fill("#msg-input", "Explain velocity in kinematics.")
            await page.click("#send-btn")

            # Wait for response output to populate
            await page.wait_for_timeout(4000)

            # ----------------------------------------------------
            # PHASE 4: MID-SESSION GROUNDING SWITCH
            # ----------------------------------------------------
            # Upload Document B
            # Simulate leaving before the completed first job's receipt was cleared.
            await page.evaluate(
                "job => localStorage.setItem(`sentio_job:${window.store.getState('currentUser').id}:library:/documents/jobs`, job)",
                first_upload["job_id"],
            )
            await page.click('a[href="#/documents"]')
            await page.wait_for_selector("#file-uploader", state="attached")
            await page.wait_for_selector("#view-documents #drop-zone", state="visible")
            await page.wait_for_function(
                "document.getElementById('file-uploader')?.disabled === false"
            )
            await page.set_input_files("#file-uploader", file_b_path)
            # Wait for list update and confirm document appears in table
            try:
                # Wait for the saved row, not the progress panel that names the file
                # while indexing is still running.
                await page.wait_for_selector(
                    '#view-documents .document-row:has-text("thermodynamics_test.txt")',
                    timeout=20000,
                )
            except Exception as exc:
                raise AssertionError(
                    (await page.locator("#view-documents").inner_text(), failed_requests)
                ) from exc

            # Go back to Tutor View
            await page.click('a[href="#/tutor"]')

            # Select Document B from sidebar grounding select dropdown
            # Wait dynamically for the options to be repopulated asynchronously
            await page.wait_for_selector(
                '#f-grounding option:has-text("thermodynamics_test.txt")',
                state="attached",
                timeout=10000,
            )

            # Switch active grounding to Document B
            val_b = await page.evaluate("""() => {
                const sel = document.querySelector("#f-grounding");
                const opt = [...sel.options].find(o => o.text.includes("thermodynamics_test.txt"));
                return opt ? opt.value : null;
            }""")
            assert val_b is not None, "thermodynamics_test.txt option value not found"
            await page.select_option("#f-grounding", value=val_b)
            await page.wait_for_timeout(1000)

            # Send a question grounded on Document B
            await page.fill("#msg-input", "What is entropy according to the document?")
            await page.click("#send-btn")
            await page.wait_for_timeout(4000)

            # ----------------------------------------------------
            # PHASE 5: SESSION RESUME VALIDATION
            # ----------------------------------------------------
            # Refresh the page to simulate closing and re-opening the browser tab
            await page.reload()
            await page.wait_for_selector("#sidebar", timeout=10000)

            # Go back to tutor view
            await page.click('a[href="#/tutor"]')
            await page.wait_for_timeout(1000)

            # Locate the resumed session item and verify it is selected/active
            active_grounding = await page.eval_on_selector(
                "#f-grounding", "sel => sel.options[sel.selectedIndex].text"
            )
            assert "thermodynamics_test.txt" in active_grounding, (
                "Grounding state was not preserved upon session resumption"
            )

            # Study history lives in the account menu in the top bar.
            await page.click(".account-btn")
            await page.click('.account-menu a[href="#/history"]')
            await page.wait_for_selector("#view-history tbody tr")
            assert "kinematics" in await page.inner_text("#view-history")
            await page.click('a[href="#/analytics"]')
            await page.wait_for_selector("text=Practice estimate")
            assert "do not prove understanding" in await page.inner_text("#view-analytics")
            screenshot = Path(__file__).resolve().parents[2] / "logs" / "browser-study.png"
            screenshot.parent.mkdir(exist_ok=True)
            await page.screenshot(path=str(screenshot))
            await browser.close()

    finally:
        server.stop()
        server.join(timeout=15)
        assert not server.is_alive(), "Browser server must release storage before the next test"
        # Clean up test files
        for p_file in [file_a_path, file_b_path]:
            if os.path.exists(p_file):
                try:
                    os.remove(p_file)
                except Exception:
                    pass


def test_unauthorized_grounding_attacks():
    """Verify adversarial API requests for invalid grounding targets return 403 or 404."""
    api_cfg.ENFORCE_AUTH = True
    with TestClient(app) as client:
        # Register User A & User B
        timestamp = int(time.time() * 1000)
        reg_a = client.post(
            f"{PREFIX}/auth/register",
            json={"email": f"usera_{timestamp}@sentio.edu", "password": "Password123!"},
        )
        login_a = client.post(
            f"{PREFIX}/auth/login",
            json={"email": f"usera_{timestamp}@sentio.edu", "password": "Password123!"},
        )
        token_a = login_a.json()["access_token"]
        student_id_a = reg_a.json()["student_id"]
        headers_a = {"Authorization": f"Bearer {token_a}"}

        client.post(
            f"{PREFIX}/auth/register",
            json={"email": f"userb_{timestamp}@sentio.edu", "password": "Password123!"},
        )
        login_b = client.post(
            f"{PREFIX}/auth/login",
            json={"email": f"userb_{timestamp}@sentio.edu", "password": "Password123!"},
        )
        token_b = login_b.json()["access_token"]
        headers_b = {"Authorization": f"Bearer {token_b}"}

        # User A creates a session
        sess_a = client.post(
            f"{PREFIX}/sessions",
            headers=headers_a,
            json={
                "student_id": student_id_a,
                "subject": "physics",
                "topic": "kinematics",
                "difficulty": "beginner",
            },
        )
        session_id_a = sess_a.json()["session_id"]

        # User B uploads a private document
        file_data = {"file": ("notes_b.txt", b"User B private study material.", "text/plain")}
        upload_b = client.post(
            f"{PREFIX}/documents/upload",
            headers=headers_b,
            files=file_data,
            data={"category": "uploaded", "subject": "physics"},
        )
        upload_b.json()["filepath"].split("/")[-1]  # filename is identifier
        # Look up document record ID for B
        docs_b = client.get(f"{PREFIX}/documents", headers=headers_b).json().get("documents", [])
        doc_b_record_id = docs_b[0]["id"]

        # ADVERSARIAL GROUNDING ATTACK 1: User A tries to ground session A on User B's private document ID
        attack1 = client.post(
            f"{PREFIX}/sessions/{session_id_a}/grounding",
            headers=headers_a,
            json={"document_id": doc_b_record_id},
        )
        # Should raise 403 Forbidden or 404 Not Found since A does not own B's document
        assert attack1.status_code in [403, 404], (
            f"Grounding attack succeeded with status {attack1.status_code}"
        )

        # ADVERSARIAL GROUNDING ATTACK 2: User A tries to ground session A on a non-existent document ID
        attack2 = client.post(
            f"{PREFIX}/sessions/{session_id_a}/grounding",
            headers=headers_a,
            json={"document_id": "non_existent_doc_id_9999"},
        )
        assert attack2.status_code in [403, 404], (
            f"Grounding non-existent attack returned {attack2.status_code}"
        )

        # ADVERSARIAL GROUNDING ATTACK 3: User B tries to change grounding of User A's session
        attack3 = client.post(
            f"{PREFIX}/sessions/{session_id_a}/grounding",
            headers=headers_b,
            json={"document_id": doc_b_record_id},
        )
        # B doesn't own session_id_a
        assert attack3.status_code == 403
