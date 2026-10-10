"""Identity boundaries using real HTTP routes/auth/SQLite, without loading ML models."""

import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from sentio.auth.middleware import get_current_user
from sentio.auth.token_manager import TokenManager
from sentio.config import KNOWN_INSECURE_SECRETS, APIConfig, api_cfg, session_cfg
from sentio.session.session_manager import SessionManager


class TestLearningIdentity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Authentication tests need neither TensorFlow nor an external model service.
        detector = SimpleNamespace(EmotionDetector=Mock(), EmotionResult=Mock())
        previous = sys.modules.get("sentio.ai.emotion_detector")
        sys.modules["sentio.ai.emotion_detector"] = detector
        try:
            with patch("sentio.shared.utils.setup_logging"):
                cls.api = importlib.import_module("sentio.api.app")
        finally:
            if previous is None:
                del sys.modules["sentio.ai.emotion_detector"]
            else:
                sys.modules["sentio.ai.emotion_detector"] = previous

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        for target, name, value in [
            (
                session_cfg,
                "DB_URL",
                "sqlite:///" + (Path(self.temp.name) / "identity.db").as_posix(),
            ),
            (session_cfg, "SESSION_LOG_PATH", Path(self.temp.name) / "sessions"),
            (api_cfg, "API_SECRET", "test-only-identity-secret-123456789"),
        ]:
            p = patch.object(target, name, value)
            p.start()
            self.addCleanup(p.stop)
        self.sm = SessionManager()
        self.sm.load()
        self.addCleanup(self.sm.persister._engine.dispose)
        for name, value in [
            ("sm", self.sm),
            ("_loaded", True),
            ("intelligence", SimpleNamespace(sm=self.sm)),
        ]:
            p = patch.object(self.api.agent, name, value)
            p.start()
            self.addCleanup(p.stop)
        limiter = patch.object(self.api.RateLimiter, "allow", return_value=True)
        limiter.start()
        self.addCleanup(limiter.stop)
        # No context manager: intentionally do not run model-loading lifespan.
        self.client = TestClient(self.api.app)
        self.addCleanup(self.client.close)
        self.prefix = self.api.PREFIX
        self.a, self.tokens_a = self.register("a")
        self.b, self.tokens_b = self.register("b")
        self.headers_a = self.headers(self.tokens_a["access_token"])
        self.headers_b = self.headers(self.tokens_b["access_token"])
        self.session_a = self.sm.create_session(self.a, "physics", "kinematics")
        self.session_b = self.sm.create_session(self.b, "physics", "kinematics")

    @staticmethod
    def headers(token):
        return {"Authorization": "Bearer " + token}

    def register(self, name):
        body = {"email": name + "@example.com", "password": "StrongPassword123!"}
        result = self.client.post(self.prefix + "/auth/register", json=body)
        self.assertEqual(result.status_code, 201, result.text)
        login = self.client.post(self.prefix + "/auth/login", json=body)
        self.assertEqual(login.status_code, 200, login.text)
        return result.json()["student_id"], login.json()

    def test_auth_is_required_even_when_legacy_switch_is_false(self):
        with patch.dict(os.environ, {"ENFORCE_AUTH": "False", "ENV": "development"}):
            self.assertTrue(APIConfig().ENFORCE_AUTH)
        with patch.object(api_cfg, "ENFORCE_AUTH", False):
            response = self.client.get(self.prefix + "/sessions", params={"student_id": self.a})
            self.assertEqual(response.status_code, 401)

    def test_token_purpose_refresh_logout_and_deleted_account(self):
        path = self.prefix + "/sessions/" + self.session_a.session_id
        self.assertEqual(self.client.get(path, headers=self.headers_a).status_code, 200)
        refresh = self.tokens_a["refresh_token"]
        self.assertEqual(self.client.get(path, headers=self.headers(refresh)).status_code, 401)
        renewed = self.client.post(self.prefix + "/auth/refresh", json={"refresh_token": refresh})
        self.assertEqual(renewed.status_code, 200)
        self.assertEqual(
            self.client.get(path, headers=self.headers(renewed.json()["access_token"])).status_code,
            200,
        )
        wrong = {"refresh_token": self.tokens_a["access_token"]}
        self.assertEqual(
            self.client.post(self.prefix + "/auth/refresh", json=wrong).status_code, 401
        )
        self.assertEqual(
            self.client.post(self.prefix + "/auth/logout", json=wrong).status_code, 400
        )
        self.assertEqual(
            self.client.post(
                self.prefix + "/auth/logout", json={"refresh_token": refresh}
            ).status_code,
            200,
        )
        self.assertEqual(self.client.get(path, headers=self.headers(refresh)).status_code, 401)
        self.assertEqual(
            self.client.post(
                self.prefix + "/auth/refresh", json={"refresh_token": refresh}
            ).status_code,
            401,
        )
        self.sm.persister.auth_repo.delete_account(self.a)
        self.assertEqual(self.client.get(path, headers=self.headers_a).status_code, 401)

    def test_private_routes_reject_anonymous_and_other_student(self):
        routes = [
            ("GET", f"/student/{self.a}/export", None),
            ("DELETE", f"/student/{self.a}/data", None),
            ("DELETE", f"/student/{self.a}/telemetry", None),
            ("GET", f"/student/{self.a}/consent", None),
            ("POST", f"/student/{self.a}/consent", {"consent_version": "1", "preferences": {}}),
            ("GET", f"/students/{self.a}/goals", None),
            ("POST", f"/students/{self.a}/goals", {"goal_text": "private goal"}),
            ("GET", f"/students/{self.a}/memory", None),
            ("GET", f"/diagnostics/session/{self.session_a.session_id}", None),
            ("POST", "/documents/sync", None),
            ("GET", "/diagnostics/structured_parser", None),
        ]
        for method, path, body in routes:
            for headers, expected in [({}, 401), (self.headers_b, 403)]:
                with self.subTest(method=method, path=path, expected=expected):
                    result = self.client.request(
                        method, self.prefix + path, json=body, headers=headers
                    )
                    self.assertEqual(result.status_code, expected, result.text)
        self.assertIsNotNone(self.sm.persister.auth_repo.get_account_by_student_id(self.a))
        self.assertEqual(self.sm.get_learning_goals(self.a), [])

    def test_owner_memory_consent_export_and_delete_still_work(self):
        student = self.prefix + "/student/" + self.a
        self.assertEqual(
            self.client.post(
                student + "/consent",
                headers=self.headers_a,
                json={"consent_version": "1", "preferences": {"telemetry": False}},
            ).status_code,
            200,
        )
        for path in [
            student + "/consent",
            student + "/export",
            self.prefix + f"/students/{self.a}/memory",
        ]:
            response = self.client.get(path, headers=self.headers_a)
            self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(
            self.client.delete(student + "/telemetry", headers=self.headers_a).status_code, 200
        )
        self.assertEqual(
            self.client.delete(student + "/data", headers=self.headers_a).status_code, 200
        )
        self.assertEqual(
            self.client.get(self.prefix + "/sessions", headers=self.headers_a).status_code, 401
        )

    def test_session_identity_cannot_be_supplied_by_body(self):
        response = self.client.post(
            self.prefix + "/sessions",
            headers=self.headers_b,
            json={"student_id": self.a, "subject": "physics", "topic": "kinematics"},
        )
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["student_id"], self.b)
        for path in [
            f"/sessions/{self.session_a.session_id}",
            f"/sessions/{self.session_a.session_id}/analytics",
        ]:
            self.assertEqual(
                self.client.get(self.prefix + path, headers=self.headers_b).status_code, 403
            )

    def test_test_identity_requires_explicit_dependency_override(self):
        self.api.app.dependency_overrides[get_current_user] = lambda: {
            "student_id": self.a,
            "role": "student",
        }
        try:
            response = self.client.get(self.prefix + "/sessions/" + self.session_a.session_id)
            self.assertEqual(response.status_code, 200)
        finally:
            self.api.app.dependency_overrides.pop(get_current_user)

    def test_expired_tampered_wrong_issuer_and_legacy_tokens_are_rejected(self):
        manager = self.sm.persister.token_manager
        payload = {"sub": self.a, "token_type": "access"}
        tokens = [
            manager.create_token(payload, -1),
            self.tokens_a["access_token"] + "tampered",
            manager.create_token({"sub": self.a}, 900),
            TokenManager(api_cfg.API_SECRET, issuer="other-app").create_token(payload, 900),
        ]
        for token in tokens:
            with self.subTest(token_kind=tokens.index(token)):
                self.assertEqual(
                    self.client.get(
                        self.prefix + "/sessions", headers=self.headers(token)
                    ).status_code,
                    401,
                )

    def test_global_operations_use_current_account_role(self):
        with patch.object(self.api.agent.sm, "get_diagnostics", return_value=[]):
            forged_role = self.sm.persister.token_manager.create_token(
                {"sub": self.a, "token_type": "access", "role": "admin"}, 900
            )
            path = self.prefix + "/diagnostics/structured_parser"
            self.assertEqual(
                self.client.get(path, headers=self.headers(forged_role)).status_code, 403
            )
            account = self.sm.persister.auth_repo.get_account_by_student_id(self.a)
            account.role = "admin"
            self.sm.persister.auth_repo.save_account(account)
            self.assertEqual(self.client.get(path, headers=self.headers_a).status_code, 200)

    def test_development_signing_key_is_not_a_public_default(self):
        from sentio.persistence.session_repository import SessionPersister

        with (
            patch.object(api_cfg, "API_SECRET", ""),
            patch.dict(os.environ, {"ENV": "development"}),
        ):
            persister = SessionPersister()
            try:
                persister.load()
                self.assertGreaterEqual(len(api_cfg.API_SECRET), 32)
                self.assertNotIn(api_cfg.API_SECRET, KNOWN_INSECURE_SECRETS)
            finally:
                if persister._engine:
                    persister._engine.dispose()

    def test_documents_and_grounding_remain_student_scoped(self):
        self.assertTrue(
            self.sm.register_document(
                {
                    "id": "doc-a",
                    "filename": "private.txt",
                    "file_type": ".txt",
                    "subject": "physics",
                    "category": "uploaded",
                    "student_id": self.a,
                    "upload_date": 1,
                    "last_modified": 1,
                    "chunk_count": 1,
                    "embedding_count": 1,
                    "status": "indexed",
                    "last_indexed": 1,
                    "checksum": "a",
                }
            )
        )
        for headers, filenames in [(self.headers_a, ["private.txt"]), (self.headers_b, [])]:
            response = self.client.get(self.prefix + "/documents", headers=headers)
            self.assertEqual(response.status_code, 200)
            self.assertEqual([d["filename"] for d in response.json()["documents"]], filenames)
        self.assertEqual(
            self.client.delete(
                self.prefix + "/documents/doc-a", headers=self.headers_b
            ).status_code,
            404,
        )
        response = self.client.post(
            self.prefix + f"/sessions/{self.session_b.session_id}/grounding",
            headers=self.headers_b,
            json={"document_id": "doc-a"},
        )
        self.assertEqual(response.status_code, 403)
        response = self.client.post(
            self.prefix + "/sessions",
            headers=self.headers_b,
            json={
                "student_id": self.b,
                "subject": "physics",
                "topic": "kinematics",
                "metadata": {"document_id": "doc-a"},
            },
        )
        self.assertEqual(response.status_code, 403)

    def test_login_normalization_keeps_returned_identity_consistent(self):
        response = self.client.post(
            self.prefix + "/auth/login",
            json={"email": " A@EXAMPLE.COM ", "password": "StrongPassword123!"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["student_id"], self.a)
        self.assertEqual(response.json()["email"], "a@example.com")

    def test_upload_cannot_escape_student_directory(self):
        with patch("sentio.api.routes.documents.BASE_DIR", Path(self.temp.name)):
            for filename in ["../private.txt", "../other/private.txt"]:
                with self.subTest(filename=filename):
                    result = self.client.post(
                        self.prefix + "/documents/upload",
                        headers=self.headers_a,
                        files={"file": (filename, b"private", "text/plain")},
                    )
                    self.assertEqual(result.status_code, 400, result.text)

    def test_foreign_quiz_is_rejected_before_grading(self):
        self.sm.save_quiz("quiz-a", self.a, self.session_a.session_id, "Private", [])
        with patch.object(self.api.quiz_service, "score_quiz", return_value={}) as score:
            response = self.client.post(
                self.prefix + "/quizzes/quiz-a/submit",
                headers=self.headers_b,
                json={"session_id": self.session_b.session_id, "answers": {}},
            )
            self.assertEqual(response.status_code, 403)
            score.assert_not_called()
            response = self.client.post(
                self.prefix + "/quizzes/quiz-a/submit",
                headers=self.headers_a,
                json={"session_id": self.session_a.session_id, "answers": {}},
            )
            self.assertEqual(response.status_code, 200)

    def test_whiteboard_overwrite_and_export_check_existing_owner(self):
        self.sm.save_whiteboard(
            "board-a", self.a, self.session_a.session_id, "Private", '{"shapes": []}'
        )
        body = {
            "whiteboard_id": "board-a",
            "student_id": self.b,
            "session_id": self.session_b.session_id,
            "title": "Overwrite",
            "canvas_state": {"width": 800, "height": 600, "shapes": []},
        }
        result = self.client.post(
            self.prefix + "/whiteboards/sessions", headers=self.headers_b, json=body
        )
        self.assertEqual(result.status_code, 403)
        self.assertEqual(self.sm.get_whiteboard("board-a")["title"], "Private")
        with patch.object(
            self.api.whiteboard_service, "export_canvas", return_value=b"png"
        ) as export:
            for headers, expected in [({}, 401), (self.headers_b, 403), (self.headers_a, 200)]:
                result = self.client.post(
                    self.prefix + "/whiteboards/board-a/export",
                    headers=headers,
                    json={"format": "png"},
                )
                self.assertEqual(result.status_code, expected)
            self.assertEqual(export.call_count, 1)

    def test_websocket_requires_owner_access_token(self):
        path = self.prefix + "/ws/" + self.session_a.session_id
        for headers in [{}, self.headers_b, self.headers(self.tokens_a["refresh_token"])]:
            with self.subTest(headers_present=bool(headers)):
                with self.assertRaises(WebSocketDisconnect):
                    with self.client.websocket_connect(path, headers=headers) as ws:
                        ws.send_json({"frame_b64": None})
                        ws.receive_json()
        with self.client.websocket_connect(path, headers=self.headers_a) as ws:
            ws.send_json({"frame_b64": None})
            self.assertIn("error", ws.receive_json())
        # Native browser WebSocket clients authenticate with their first message.
        with self.client.websocket_connect(path) as ws:
            ws.send_json({"access_token": self.tokens_a["access_token"]})
            ws.send_json({"frame_b64": None})
            self.assertIn("error", ws.receive_json())
            self.sm.persister.auth_repo.delete_account(self.a)
            ws.send_json({"frame_b64": None})
            with self.assertRaises(WebSocketDisconnect):
                ws.receive_json()


if __name__ == "__main__":
    unittest.main()
