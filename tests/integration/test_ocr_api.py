from fastapi.testclient import TestClient

from sentio.api.app import agent, app
from sentio.ingestion import ocr
from tests.helpers import login_student


def test_ocr_upload_missing_tool_returns_setup_error_and_preserves_original(monkeypatch):
    from sentio.api.routes import documents

    agent.load()
    monkeypatch.setattr(ocr, "tesseract_path", lambda: None)
    with TestClient(app) as client:
        sid = login_student(client)
        path = documents.BASE_DIR / "data/documents" / sid / "uploaded/scan.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"previous learner file")
        from io import BytesIO

        from PIL import Image

        content = BytesIO()
        Image.new("RGB", (100, 100), "white").save(content, format="PNG")
        response = client.post(
            "/api/v1/documents/upload",
            files={"file": ("scan.png", content.getvalue(), "image/png")},
        )
        assert response.status_code == 422
        assert "Tesseract" in response.json()["detail"]
        assert path.read_bytes() == b"previous learner file"
        assert not client.get("/api/v1/documents/capabilities").json()["ocr_available"]
