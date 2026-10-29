import uuid

from fastapi.testclient import TestClient

from sentio.api.app import app


def test_standard_jwt_and_legacy_sign_in_validation():
    import hashlib
    import hmac
    import json
    import time

    import jwt
    import pytest

    from sentio.auth.exceptions import InvalidTokenError
    from sentio.auth.token_manager import TokenManager

    manager = TokenManager("test-jwt-signing-key-with-at-least-64-bytes-for-all-test-algorithms!!")
    token = manager.create_token({"sub": "learner", "token_type": "access"}, 900)
    assert (
        jwt.decode(token, manager.secret_key, algorithms=["HS256"], issuer="sentio")["sub"]
        == "learner"
    )
    assert jwt.get_unverified_header(token)["typ"] == "JWT"
    header = manager._base64_url_encode(json.dumps({"alg": "HS256", "typ": "SEN"}).encode())
    payload = manager._base64_url_encode(
        json.dumps({"sub": "learner", "iss": "sentio", "exp": time.time() + 900}).encode()
    )
    message = header + "." + payload
    legacy = (
        message + "." + hmac.new(manager.secret_key, message.encode(), hashlib.sha256).hexdigest()
    )
    assert manager.verify_token(legacy)["sub"] == "learner"
    for forged in (
        legacy[:-3] + "bad",
        jwt.encode({"iss": "sentio", "exp": float("inf")}, manager.secret_key, algorithm="HS256"),
        jwt.encode(
            {"iss": "sentio", "exp": time.time() + 900}, manager.secret_key, algorithm="HS384"
        ),
    ):
        with pytest.raises(InvalidTokenError):
            manager.verify_token(forged)


def test_legacy_password_hashes_still_verify_and_upgrade_on_login():
    import hashlib

    from sentio.api.app import agent

    with TestClient(app) as client:
        email = f"legacy-hash-{uuid.uuid4().hex}@example.com"
        password = "LegacyPassword123!"
        account = client.post(
            "/api/v1/auth/register", json={"email": email, "password": password}
        ).json()
        stored = agent.sm.persister.auth_repo.get_account_by_student_id(account["student_id"])
        salt = bytes.fromhex("0123456789abcdef0123456789abcdef")
        stored.password_hash = (
            salt.hex() + "$" + hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100000).hex()
        )
        agent.sm.persister.auth_repo.save_account(stored)
        assert (
            client.post(
                "/api/v1/auth/login", json={"email": email, "password": password}
            ).status_code
            == 200
        )
        upgraded = agent.sm.persister.auth_repo.get_account_by_student_id(account["student_id"])
        assert upgraded.password_hash.startswith("pbkdf2_sha256$600000$")
        assert (
            client.post(
                "/api/v1/auth/reset-password",
                json={
                    "email": email,
                    "recovery_key": account["recovery_key"],
                    "new_password": "ReplacementPassword123!",
                },
            ).status_code
            == 200
        )


def test_recovery_is_single_use_preserves_notes_and_revokes_old_sessions():
    with TestClient(app) as client:
        email = f"recovery-{uuid.uuid4().hex}@example.com"
        credentials = {"email": email, "password": "OriginalPassword123!"}
        account = client.post("/api/v1/auth/register", json=credentials).json()
        key = account["recovery_key"]
        assert len(key) >= 32
        tokens = client.post("/api/v1/auth/login", json=credentials).json()
        headers = {"Authorization": "Bearer " + tokens["access_token"]}
        assert (
            client.post(
                "/api/v1/documents/upload",
                headers=headers,
                files={
                    "file": ("retained.txt", b"Inertia resists changes in velocity.", "text/plain")
                },
            ).status_code
            == 201
        )
        reset = {"email": email, "recovery_key": key, "new_password": "ReplacementPassword123!"}
        bad = client.post(
            "/api/v1/auth/reset-password", json={**reset, "recovery_key": "invalid-recovery-key"}
        )
        unknown = client.post(
            "/api/v1/auth/reset-password", json={**reset, "email": "absent@example.com"}
        )
        assert bad.status_code == unknown.status_code == 401
        assert bad.json() == unknown.json()
        changed = client.post("/api/v1/auth/reset-password", json=reset)
        assert changed.status_code == 200, changed.text
        assert changed.headers["cache-control"] == "no-store"
        assert changed.json()["recovery_key"] != key
        assert client.post("/api/v1/auth/reset-password", json=reset).status_code == 401
        assert client.get("/api/v1/documents", headers=headers).status_code == 401
        assert (
            client.post(
                "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
            ).status_code
            == 401
        )
        assert client.post("/api/v1/auth/login", json=credentials).status_code == 401
        fresh = client.post(
            "/api/v1/auth/login", json={"email": email, "password": reset["new_password"]}
        )
        assert fresh.status_code == 200
        saved = client.get(
            "/api/v1/documents", headers={"Authorization": "Bearer " + fresh.json()["access_token"]}
        )
        assert saved.status_code == 200 and saved.json()["count"] == 1
