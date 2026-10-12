from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from sentio.api.app import http_failure, unhandled_failure
from sentio.api.middleware import BodyLimitMiddleware, ResponseHeadersMiddleware


def test_actual_chunked_bytes_are_limited_before_parsing_and_errors_are_safe():
    app = FastAPI()
    app.add_exception_handler(HTTPException, http_failure)
    app.add_exception_handler(Exception, unhandled_failure)
    app.add_middleware(BodyLimitMiddleware, json_limit=10, upload_limit=20)
    app.add_middleware(ResponseHeadersMiddleware)

    @app.post("/json")
    async def read_json(request: Request):
        return {"length": len(await request.body())}

    @app.get("/failure")
    def failure():
        raise HTTPException(500, "private database path and credential")

    @app.post("/documents/upload")
    async def upload(file: UploadFile = File(...)):
        return {"length": len(await file.read())}

    @app.get("/unhandled")
    def unhandled():
        raise OperationalError("private SQL", {"secret": "private credential"}, Exception("disk"))

    with TestClient(app, raise_server_exceptions=False) as client:
        assert client.post("/json", content=b"tiny").status_code == 200
        assert client.post("/json", content=b"x" * 11).status_code == 413
        assert client.post("/json", content=iter([b"x" * 6, b"y" * 6])).status_code == 413
        multipart = [
            b'--boundary\r\nContent-Disposition: form-data; name="file"; filename="notes.txt"\r\n\r\n',
            b"x" * 100,
            b"\r\n--boundary--\r\n",
        ]
        assert (
            client.post(
                "/documents/upload",
                content=iter(multipart),
                headers={"Content-Type": "multipart/form-data; boundary=boundary"},
            ).status_code
            == 413
        )
        assert (
            client.post("/json", content=b"", headers={"Content-Length": "bad"}).status_code == 400
        )
        for path in ("/failure", "/unhandled"):
            response = client.get(path)
            assert response.status_code == 500
            assert "private" not in response.text
            assert "Retry" in response.json()["detail"]
        response = client.post("/json", content=b"tiny")
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["Referrer-Policy"] == "no-referrer"
