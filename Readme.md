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
unavailable. Optional English OCR supports scanned or mixed PDFs and PNG/JPEG
images, with page citations and text/OCR/mixed extraction provenance. OCR processes
at most 20 scanned pages per document and rejects encrypted or unreadable files.
Native PDF text is preserved. The OCR engine must be installed locally.

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

## Reproducible AI evaluations

The versioned, author-written corpus contains 22 retrieval cases (including
paraphrases, irrelevant questions and adversarial instructions) and 14 grading
rubrics. Evaluations create a temporary database, register and authenticate a
learner, index only the selected fixture documents, and clean up afterward.
They do not scan learner uploads or score simulated answers.

```powershell
uv run python scripts/evaluate_retrieval.py --grade --output reports/evaluation.json
uv run python scripts/benchmark_ollama_cpu.py --repetitions 3 --cases 3 --output reports/latency.json
```

The embedding model must already be cached for the retrieval benchmark; the
semantic grading and CPU latency experiments require local Ollama. See
[measured evaluation results](reports/AI_EVALUATION_2026-10-11.md) and
[CPU experiment results](reports/CPU_LATENCY_2026-10-11.md). These are small
synthetic experiments, not guarantees of answer quality or emotion accuracy.

## Optional local OCR

```powershell
uv sync --extra ocr
```

Install Tesseract with English (`eng`) language data using your OS package
manager. On Windows, the standard `C:\Program Files\Tesseract-OCR` location is
detected; alternatively set `TESSERACT_CMD` to the executable's absolute path.
On Ubuntu: `sudo apt-get install tesseract-ocr tesseract-ocr-eng`.
Use `uv run --extra ocr sentio --port 8001` to retain the optional dependency.
The Document Library shows whether OCR is available and how each document was
extracted. Image OCR is capped at 16 million pixels; PDF rendering is capped at
that size and starts at 150 DPI. Rotated images are tried in four orientations.
The native text heuristic treats pages with fewer than 10 non-whitespace
characters as OCR candidates; complex layouts may require a cleaner scan.

Run all OCR regressions with `uv run --extra ocr python scripts/run_tests.py -q`.
CI installs Tesseract and the OCR extra, including a live generated-image test.
The local Tesseract installation was canceled, so its live test is currently
skipped on this machine; fixture tests validate PDFium rendering, orientation
selection, limits, provenance and actionable errors.
Docker OCR is optional: `docker build --build-arg ENABLE_OCR=1 -t sentio-ocr .`.
Docker has not been verified on this machine. See the
[dependency decision](docs/OCR_DEPENDENCY_DECISION.md) for resource and license details.
