import time

from fastapi.testclient import TestClient

from sentio.api.app import agent, app
from tests.helpers import login_student


def finished(client, job):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        current = client.get("/api/v1/jobs/" + job["job_id"]).json()
        if current["status"] in ("succeeded", "failed", "cancelled"):
            return current
        time.sleep(0.03)
    raise AssertionError("Ingestion did not finish")


def test_ingestion_jobs_are_owned_and_previews_are_paginated():
    with TestClient(app) as client:
        login_student(client)
        owner_header = dict(client.headers)
        content = ("Inertia keeps motion unchanged without an external net force. " * 30).encode()
        response = client.post(
            "/api/v1/documents/jobs",
            files={"file": ("inertia.txt", content, "text/plain")},
            data={"category": "notes"},
        )
        assert response.status_code == 202, response.text
        job = finished(client, response.json())
        assert job["status"] == "succeeded", job
        document_id = job["result"]["document_id"]
        preview = client.get("/api/v1/documents/" + document_id + "/preview?limit=1").json()
        assert len(preview["chunks"]) == 1 and preview["next_offset"] == 1
        assert "external net force" in preview["chunks"][0]["text_content"]
        assert (
            client.get("/api/v1/documents/" + document_id + "/preview?limit=101").status_code == 422
        )
        login_student(client)
        assert client.get("/api/v1/documents/" + document_id + "/preview").status_code == 404
        assert client.get("/api/v1/jobs/" + job["job_id"]).status_code == 404
        client.headers.update(owner_header)
        assert client.delete("/api/v1/documents/" + document_id).status_code == 200
        assert agent.sm.get_document_chunks(document_id) == []
        assert client.get("/api/v1/documents/" + document_id + "/preview").status_code == 404


def test_empty_replacement_job_preserves_existing_note():
    with TestClient(app) as client:
        owner = login_student(client)
        first = client.post(
            "/api/v1/documents/upload",
            files={"file": ("same.txt", b"An original account of inertia.", "text/plain")},
        ).json()
        previous = agent.sm.list_documents(student_id=owner)
        chunks = agent.sm.get_document_chunks(first["document_id"])
        response = client.post(
            "/api/v1/documents/jobs", files={"file": ("same.txt", b"", "text/plain")}
        )
        assert response.status_code == 202
        assert finished(client, response.json())["status"] == "failed"
        assert agent.sm.list_documents(student_id=owner) == previous
        assert agent.sm.get_document_chunks(first["document_id"]) == chunks


def test_retried_upload_submission_replays_owned_job_and_rejects_changed_file():
    with TestClient(app) as client:
        owner = login_student(client)
        headers = {"Idempotency-Key": "upload-intent-one"}
        files = {"file": ("retry-safe.txt", b"Inertia preserves uniform motion.", "text/plain")}
        first = client.post("/api/v1/documents/jobs", headers=headers, files=files)
        repeated = client.post("/api/v1/documents/jobs", headers=headers, files=files)
        assert first.status_code == repeated.status_code == 202
        assert first.json()["job_id"] == repeated.json()["job_id"]
        assert finished(client, first.json())["status"] == "succeeded"
        assert len(agent.sm.list_documents(student_id=owner)) == 1
        assert (
            client.post(
                "/api/v1/documents/jobs",
                headers=headers,
                files={"file": ("retry-safe.txt", b"Different evidence.", "text/plain")},
            ).status_code
            == 409
        )
        assert (
            client.post(
                "/api/v1/documents/jobs", headers={"Idempotency-Key": "bad"}, files=files
            ).status_code
            == 422
        )
