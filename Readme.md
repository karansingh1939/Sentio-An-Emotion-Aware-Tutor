# Sentio

A local emotion-aware tutor with document-grounded learning and study tools. The Python server also serves the web interface;
there is no separate npm development server.

## Run on this Windows checkout

Open a PowerShell terminal and run:

```powershell
cd "C:\ai project"
python scripts/dev_start.py --port 8001
```

Wait for `Application startup complete`, then open <http://127.0.0.1:8001>.
Leave the terminal open; press Ctrl+C to stop the server. The launcher uses
the project's `.venv` automatically, so activation is unnecessary.
Port 8001 avoids the other service currently occupying port 8000.
Use `--port 8000` if that port is free. Add `--reload` for development.

## First-time setup or missing dependencies

Install Python 3.12, uv, and Ollama, then run from the project root:

```powershell
uv sync
```

If `.env` does not exist, copy `.env.example` to `.env`. For local AI tutoring,
set `LLM_BACKEND=ollama` and `OLLAMA_MODEL=phi3:mini` in `.env`.
Start the Ollama app (or `ollama serve` in another terminal if it is not
already running), then install the configured model if missing:

```powershell
ollama pull phi3:mini
uv run sentio --port 8001
```

Ollama and `phi3:mini` are already available on this machine. Initial server
startup can take about a minute while the machine-learning libraries load.

## Checks

```powershell
uv run python scripts/check_environment.py
uv run playwright install chromium
uv run python scripts/run_tests.py -q
npm ci
npm test
uv run ruff check src scripts tests
uv run ruff format --check src scripts tests
npm run format:check
uv build
```

Tests use temporary databases and deterministic provider fixtures. The browser
suite runs real Chromium against the API and checks registration, uploads,
document grounding, source switching, session restoration, History, and Analytics.
It does not require paid API credentials or modify learner documents.

If plain `python -m sentio` reports `No module named sentio`, use the launcher
above, `uv run sentio`, or `.\.venv\Scripts\python.exe -m sentio`.

## Docker

Install Docker with Compose first. Set a random secret, start Ollama, and pull
the model before starting the tutor:

```powershell
$env:API_SECRET = python -c "import secrets; print(secrets.token_hex(32))"
docker compose up -d ollama
docker compose exec ollama ollama pull phi3:mini
docker compose up --build -d sentio-api
```

Open <http://127.0.0.1:8000>. Keep the same secret across restarts if existing
logins should remain valid. Data and emotion model weights use the host `data/`
and `models/` directories. Docker and CI use `uv.lock`, with no separate
requirements file. The Docker build has not been run on this Windows machine
because Docker is not installed.

## Current capabilities and limits

PDF, DOCX, and TXT uploads are available to their authenticated owner. Files
are limited to 20 MiB. Text remains searchable by keywords when embeddings are
unavailable. Scanned PDFs need OCR and currently return a clear extraction error.
Image uploads are unsupported.

The AI provider must be running for generation and semantic answer grading.
Objective quiz answers still produce deterministic grades when the summary
provider is unavailable. Identical quiz submissions return their saved result;
changed answers are a new attempt. History shows the latest 50 sessions.

Camera features are optional and require browser permission. Model weights
loading successfully does not establish emotion recognition accuracy. A real
webcam and a representative labelled dataset are needed to validate that feature.

See [the repair and improvement report](docs/FIX_REPORT_2026-10-11.md) for
validation evidence and the next priorities.

## Architecture

Browser SPA ? authenticated FastAPI routes ? tutor/study services ? SQLite and
Qdrant. Ollama supplies local text generation; the optional camera pathway uses
the emotion detector. Document extraction feeds both keyword and vector retrieval.

The `src/sentio` package contains API, AI, retrieval, ingestion, study services,
and static web assets. `tests/` contains unit, integration, and browser checks.
`scripts/` contains development, evaluation, and benchmark entry points.

## Provenance and portfolio development

This project builds on [AayushiNagar2411/Sentio-An-Emotion-Aware-Tutor](https://github.com/AayushiNagar2411/Sentio-An-Emotion-Aware-Tutor).
The original history, authorship, and MIT license are preserved. Karan Singh's
current development adds the package/lockfile migration, reliable authenticated
study flows, privacy cleanup, regression coverage, and working History/Analytics.
AI-assisted implementation is checked with tests and local runtime verification.

The next milestones are reproducible retrieval/grading evaluations, measured
local inference improvements, and optional OCR. Results will describe the actual
hardware, dataset, model, and limits; successful model loading is not an accuracy
claim. Commits use their real dates. See [development record](docs/DEVELOPMENT_LOG.md).
