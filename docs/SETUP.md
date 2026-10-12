# Setup and operation

Sentio runs locally using Python 3.12, uv, and Ollama. The API serves the bundled browser interface; a separate npm development server is unnecessary. Node.js 22 supports frontend formatting and tests.

## Local installation

Follow the [README quick start](../Readme.md#quick-start). Copy `.env.example` to `.env`; use `LLM_BACKEND=ollama` and `OLLAMA_MODEL=phi3:mini`. Start the Ollama application or run `ollama serve`, then install the configured model with `ollama pull phi3:mini`.

```sh
uv sync --locked
uv run sentio --port 8001
```

Open http://127.0.0.1:8001 after application startup completes. Use another free port if necessary. For development, add `--reload`. The launcher `python scripts/dev_start.py --port 8001` selects the checkout's `.venv` automatically on Windows, Linux, and macOS.

`GET /api/v1/ready` reports storage, configured Ollama model, retrieval, OCR, and optional camera separately. Saved materials remain usable when AI is unavailable. Normal startup does not load TensorFlow or camera weights.

## Configuration and data

The default checkout stores runtime files under `data/`, `models/`, and `logs/`. Set `SENTIO_HOME` to a separate runtime directory when needed; its `.env` supplies configuration. Installed packages default to `~/.sentio`. Keep these directories and signing secrets private.

Development creates a local secret when none is configured. Production requires a random, stable `API_SECRET`; generate one using `python -c "import secrets; print(secrets.token_hex(32))"`. Retaining the signing secret across restarts preserves token validity. Do not commit it.

Run one server process per persistent home. The storage lease prevents two processes from simultaneously owning the same SQLite installation. Generation uses a bounded local worker; this is not a multi-worker hosted deployment.

## Docker Compose

Install Docker with Compose. Container execution was not verified locally during the recorded development checkpoints. The repository's Docker CI job checks builds; it does not establish live model quality or a full Compose journey.

In PowerShell, set a random secret for this terminal:

```powershell
$env:API_SECRET = python -c "import secrets; print(secrets.token_hex(32))"
```

In Linux/macOS shells:

```sh
export API_SECRET="$(python -c 'import secrets; print(secrets.token_hex(32))')"
```

Then run:

```sh
docker compose config --quiet
docker compose up -d ollama
docker compose exec ollama ollama pull phi3:mini
docker compose up --build -d sentio-api
```

Open http://127.0.0.1:8000. Host `data/` and `models/` directories retain application data; a named volume retains Ollama models. Set `OLLAMA_MODEL` if selecting another model, and pull that exact model before starting the API. Keep the same signing secret across restarts.

Stop using `docker compose down`. Deleting model volumes or host data removes saved content. Compose binds port 8000 on the host; keep the installation on a trusted local network. Consult [security guidance](../SECURITY.md) before exposing it publicly.

## Optional English OCR

```sh
uv sync --locked --extra ocr
uv run --extra ocr sentio --port 8001
```

Install Tesseract with `eng` language data separately. On Ubuntu: `sudo apt-get install tesseract-ocr tesseract-ocr-eng`. On Windows, the standard `C:\Program Files\Tesseract-OCR` location is detected; alternatively set `TESSERACT_CMD` to the executable's absolute path.

Docker OCR: `docker build --build-arg ENABLE_OCR=1 -t sentio-ocr .`. The default Compose build does not enable OCR.

Native PDF text is preserved. OCR supports scanned/mixed PDFs and PNG/JPEG images, capped at 20 scanned pages and 16 million pixels per rendered page/image. Uploads are limited to 20 MiB. Encrypted or unreadable files are rejected. Extraction provenance and page citations are saved. See [OCR dependency decisions](OCR_DEPENDENCY_DECISION.md) and [measured synthetic results](../reports/OCR_EVALUATION_2026-10-11.md).

## Backup and restore

Stop Sentio before creating a snapshot. Backups contain private data and secrets; keep them local. Replace the example paths with your runtime home and chosen backup locations.

```powershell
uv run python scripts/backup_local.py create "C:\path\to\sentio" "C:\private-backups\snapshot"
uv run python scripts/backup_local.py verify "C:\private-backups\snapshot"
uv run python scripts/backup_local.py restore "C:\private-backups\snapshot" "C:\private-backups\restored-home"
```

Restore only into an empty directory. Set `SENTIO_HOME` to the restored directory before starting the application.

## Troubleshooting

| Symptom                  | Action                                                                        |
| ------------------------ | ----------------------------------------------------------------------------- |
| `No module named sentio` | Use `uv run sentio` or the development launcher after `uv sync --locked`      |
| Port already occupied    | Choose another port with `--port` or adjust the Compose host mapping          |
| Generation unavailable   | Check Ollama, the exact model name, and `/api/v1/ready`                       |
| Storage already in use   | Stop the other server using that runtime home before restarting or backing up |
| OCR unavailable          | Install Tesseract, English data, and the OCR extra; check `TESSERACT_CMD`     |
| Slow first launch        | Allow library/model initialization; inspect readiness and local logs          |

For normal study use, follow the [learner guide](STUDY_GUIDE.md). For supported boundaries and unfinished work, see [release handoff](RELEASE_HANDOFF.md).
