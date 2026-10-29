import time
import unittest

from fastapi.testclient import TestClient

from sentio.api.app import PREFIX, app
from sentio.config import api_cfg


class TestTenantIsolation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Explicitly restore the standard test database configuration
        from sentio.api.app import agent

        agent._loaded = False
        agent.load()

    def setUp(self):
        # Force auth enforcement for security tests
        self.original_enforce = getattr(api_cfg, "ENFORCE_AUTH", False)
        api_cfg.ENFORCE_AUTH = True

    def tearDown(self):
        # Restore auth enforcement
        api_cfg.ENFORCE_AUTH = self.original_enforce

    def test_two_user_resource_isolation(self):
        """Verify User B cannot access User A's sessions, files or flashcards."""
        with TestClient(app) as client:
            timestamp = int(time.time() * 1000)
            email_a = f"usera_{timestamp}@sentio.edu"
            email_b = f"userb_{timestamp}@sentio.edu"
            password = "StrongPassword123!"

            # 1. Register and Login User A
            reg_a = client.post(
                f"{PREFIX}/auth/register", json={"email": email_a, "password": password}
            )
            self.assertEqual(reg_a.status_code, 201)
            student_id_a = reg_a.json()["student_id"]
            login_a = client.post(
                f"{PREFIX}/auth/login", json={"email": email_a, "password": password}
            )
            self.assertEqual(login_a.status_code, 200)
            token_a = login_a.json()["access_token"]
            headers_a = {"Authorization": f"Bearer {token_a}"}

            # 2. Register and Login User B
            reg_b = client.post(
                f"{PREFIX}/auth/register", json={"email": email_b, "password": password}
            )
            self.assertEqual(reg_b.status_code, 201)
            student_id_b = reg_b.json()["student_id"]
            login_b = client.post(
                f"{PREFIX}/auth/login", json={"email": email_b, "password": password}
            )
            self.assertEqual(login_b.status_code, 200)
            token_b = login_b.json()["access_token"]
            headers_b = {"Authorization": f"Bearer {token_b}"}

            # 3. Create Session for User A
            sess_a_resp = client.post(
                f"{PREFIX}/sessions",
                headers=headers_a,
                json={
                    "student_id": student_id_a,
                    "subject": "physics",
                    "topic": "kinematics",
                    "difficulty": "beginner",
                },
            )
            self.assertEqual(sess_a_resp.status_code, 201)
            session_id_a = sess_a_resp.json()["session_id"]

            # 4. Attempt to access or modify User A's session using User B's credentials
            # A. Retrieve session details
            get_sess_b = client.get(f"{PREFIX}/sessions/{session_id_a}", headers=headers_b)
            self.assertEqual(get_sess_b.status_code, 403)

            # B. Send chat message to User A's session
            chat_sess_b = client.post(
                f"{PREFIX}/sessions/{session_id_a}/chat",
                headers=headers_b,
                json={"message": "Hack attempt"},
            )
            self.assertEqual(chat_sess_b.status_code, 403)

            # C. Close User A's session
            close_sess_b = client.delete(f"{PREFIX}/sessions/{session_id_a}", headers=headers_b)
            self.assertEqual(close_sess_b.status_code, 403)

            # 5. Upload Document for User A
            file_data = {"file": ("notes_a.txt", b"User A private kinematics notes.", "text/plain")}
            upload_a = client.post(
                f"{PREFIX}/documents/upload",
                headers=headers_a,
                files=file_data,
                data={"category": "uploaded", "subject": "physics"},
            )
            self.assertEqual(upload_a.status_code, 201)

            # A. Verify User B listing does not show User A's document
            list_b = client.get(f"{PREFIX}/documents", headers=headers_b)
            self.assertEqual(list_b.status_code, 200)
            self.assertNotIn(
                "notes_a.txt", [d["filename"] for d in list_b.json().get("documents", [])]
            )

            # B. Attempt to delete User A's document using User B's credentials
            docs_a = (
                client.get(f"{PREFIX}/documents", headers=headers_a).json().get("documents", [])
            )
            doc_id_real = docs_a[0]["id"]
            delete_b = client.delete(f"{PREFIX}/documents/{doc_id_real}", headers=headers_b)
            self.assertEqual(delete_b.status_code, 404)  # Not Found / Access Denied

            # 6. Create Flashcards for User A
            deck_a = client.post(
                f"{PREFIX}/flashcards/decks",
                headers=headers_a,
                json={"student_id": student_id_a, "deck_name": "Kinematics Deck"},
            )
            self.assertEqual(deck_a.status_code, 201)
            deck_id_a = deck_a.json()["deck_id"]

            # A. Attempt to create cards in User A's deck using User B's credentials
            gen_cards_b = client.post(
                f"{PREFIX}/flashcards/generate",
                headers=headers_b,
                json={
                    "student_id": student_id_b,
                    "deck_id": deck_id_a,
                    "topic_id": "kinematics",
                    "num_cards": 2,
                },
            )
            # Since the deck check is based on student ownership:
            self.assertEqual(gen_cards_b.status_code, 403)

            # B. List User A's due reviews using User B's credentials
            due_b = client.get(
                f"{PREFIX}/flashcards/reviews/due?deck_id={deck_id_a}", headers=headers_b
            )
            # Should filter/deny due cards for B
            self.assertEqual(due_b.json().get("due_count", 0), 0)
