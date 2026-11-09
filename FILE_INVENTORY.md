# Sentio file inventory (2026-11-09)

All 443 files tracked by git, grouped by folder. For each one: what it does, and whether it needs to stay.

**Verdicts**
- **Keep**: the app, the tests, the build or CI needs it, or another doc links to it.
- **Review**: still works or is still linked, but out of date. Archive it or delete it. Your call.
- **Remove?**: nothing uses it or links to it.

Ignored folders (`data/`, `backups/`, `models/`, `logs/`, `.venv/`, `node_modules/`, `.env`, `tmp/real-samples/`) aren't in git and aren't listed here. Sentio needs them at runtime or they hold your own data.

---

## 1. Root config and project files

| File | Use | Verdict |
|---|---|---|
| `pyproject.toml` | Python package definition: dependencies, the `sentio` command, pytest and ruff settings | Keep |
| `uv.lock` | Pins exact Python dependency versions so installs are repeatable | Keep |
| `.python-version` | Tells uv to use Python 3.12 | Keep |
| `package.json` | Node scripts for the frontend tests (`npm test`) and Prettier formatting | Keep |
| `package-lock.json` | Pins the Prettier version | Keep |
| `.prettierrc.json` | Prettier formatting rules for JS/CSS/HTML | Keep |
| `.editorconfig` | Indentation and line-ending defaults for any editor | Keep |
| `.gitattributes` | Line-ending rules for git (stops Windows CRLF churn) | Keep |
| `.gitignore` | Keeps data, models, caches, secrets and scratch out of git | Keep |
| `.env.example` | Template for your `.env` (port, model, auth settings) | Keep |
| `Dockerfile` | Builds the container image; CI builds it on every push | Keep |
| `docker-compose.yml` | Runs Sentio and Ollama together; CI smoke-tests it | Keep |
| `.dockerignore` | Keeps data and caches out of the Docker image | Keep |
| `README.md` | Project front page: what Sentio is, screenshots, how to run it | Keep |
| `LICENSE` | MIT licence, required because the code reuses the original Sentio project | Keep |
| `CONTRIBUTING.md` | How to set up, lint and test before a change | Keep |
| `SECURITY.md` | How to report a security problem; GitHub shows it on the repo | Keep |
| `PRODUCT.md` | Product brief: who it's for and what it must do | Keep |
| `DESIGN.md` | The design system (colours, type, layout, motion); 15 files refer to it | Keep |
| `.impeccable/config.json` | Settings for the Impeccable design checker, including one approved exception in `theme.css` | Keep |
| `.impeccable/design.json` | Design tokens the Impeccable tool reads with DESIGN.md | Keep |

## 2. `.github/`

| File | Use | Verdict |
|---|---|---|
| `workflows/ci.yml` | CI: lint, Python and JS tests, OCR check, Docker build | Keep |
| `ISSUE_TEMPLATE/bug_report.yml` | Form GitHub shows when someone opens a bug | Keep |
| `ISSUE_TEMPLATE/feature_request.yml` | Form for feature requests | Keep |
| `pull_request_template.md` | Checklist pre-filled into every PR | Keep |

## 3. `src/sentio/`: the application (all Keep)

I checked every Python module: each one is imported by the app, the tests or a script. Nothing in `src/` is dead.

**Entry points.** `__init__.py` marks the package. `__main__.py` runs `python -m sentio` and the `sentio` command. `config.py` holds all settings read from `.env`.

**`api/`** (the web server)
- `app.py`: builds the FastAPI app and mounts every router and the static frontend.
- `dependencies.py`: shared services and the "does this user own this item" checks.
- `middleware.py`: request IDs, security headers, rate limiting.
- `schemas.py`: validates request bodies.
- `routes/` has one file per feature: `auth`, `courses`, `documents`, `topics`, `slides`, `syllabus`, `planning`, `sessions`, `tutoring`, `streaming` (live answers), `quizzes`, `flashcards`, `jobs` (background work), `intelligence` (mastery and learning path), `memory`, `analytics`, `emotion` (camera), `privacy` (export and delete), `system` (health).

**`ai/`** (talking to the model)
- `providers.py`: Ollama and other model backends.
- `tutor_llm.py`: tutor model calls.
- `prompts.py`: prompt text.
- `grounding.py`: checks citations against your notes.
- `structured_parser.py`, `response_parser.py`, `response_models.py`, `stream_schema.py`: turn model output into safe, validated JSON, including while it streams.
- `practice_schema.py`: makes quiz and card batches the size you asked for.
- `source_practice.py`: fallback practice built straight from your notes when the model fails.
- `conversation_history.py`: chat history for a session.

**`auth/`** (accounts): `service.py` (sign-up and sign-in), `token_manager.py` (login tokens), `password_hasher.py`, `validators.py`, `recovery.py` (recovery keys), `local_secret.py` (signing key on disk), `permissions.py`, `middleware.py`, `models.py`, `repositories.py` (database access), `audit.py` (security log), `exceptions.py`.

**`ingestion/`** (uploading notes): `pipeline.py` reads PDF, DOCX, PPTX and TXT and splits them into chunks. `ocr.py` is optional OCR for scanned notes. `recovery.py` makes uploads crash-safe.

**`rag/`** (finding the right passages): `knowledge_base.py` (search over your notes), `vector_db.py` (Qdrant embeddings), `bm25.py` (keyword search), `reranker.py`, `evidence_policy.py` (is this passage relevant enough).

**`tutor/`** (the study session): `agent.py` (the core tutor), `orchestrator.py`, `stream_service.py` (cancellable streamed turns), `difficulty.py` (when difficulty changes), `slides.py` (explaining one slide).

**`study/`**: `topics.py` (topics in a lecture), `syllabus.py` (matches a syllabus to your topics), `planning.py` (what to revise next), `overview.py` (document summary).

**`intelligence/`** (learning model): `mastery.py`, `forgetting.py`, `confidence.py`, `misconception.py`, `adaptation.py`, `recommendation.py`, `learning_path.py`, `progress.py`, `explanation.py`, `session_summary.py`, `models.py`, `service.py`.

**`quiz/service.py`** and **`flashcards/`** (`service.py`, `fsrs.py`, the spaced-repetition scheduler): quizzes and flashcards.

**`session/`**: `manager.py`, `models.py`, `analytics.py`. These track study sessions.

**`jobs/`**: `service.py` and `control.py`. Background work (quiz generation and similar) you can cancel.

**`repositories/`**: database tables and queries for courses, documents, topics, slides, syllabus, planning, practice, quizzes, sessions and jobs. `migrations.py` upgrades older databases.

**`emotion/`** (optional camera): `detector.py` (face/emotion model), `policy.py` (turns readings into a study mood), `access.py` (consent and limits).

**`maintenance/`**: `backup.py`, `account_cleanup.py`, `health_check.py`, `readiness.py`, `storage_lease.py` (stops two app copies sharing one database).

**`shared/`**: `exceptions.py`, `logging_setup.py`, `rate_limit.py`, `text.py`.

**`evaluation/`**: offline experiment code used by `scripts/eval/` (retrieval, OCR, latency, grading, evidence model, study quality, plus `evidence_review.html`, the labelling page). Not used by the running app, but the tests and the portfolio numbers depend on it.

**`static/`** (the frontend the server sends to the browser)
- `index.html`: the single page.
- `css/theme.css`, `workspace.css`, `styles.css`: the styles.
- `fonts/Outfit-Variable.ttf` and its licence `OFL.txt`.
- `img/favicon.svg`, `sentio-symbol.svg`, `sentio-wordmark.svg`: brand images.
- `js/app.js`: starts the app.
- `js/core/`: `api` (server calls), `router`, `store` (state), `jobs`, `tutor_runtime` (live answers), `emotion_camera`, `motion`, `icons`, `html` (safe escaping), `workspace`.
- `js/components/`: `ui.js`, `recovery.js`.
- `js/views/`: one per screen: `today`, `library`, `study`, `slides`, `quizzes`, `flashcards`, `progress`, `history`, `settings`, `auth`.
- `js/dev/data_fixtures.js`: fake data for the worst-case/demo view during design checks.

## 4. `tests/` (all Keep)

| Folder | Use |
|---|---|
| `unit/` (45 files) | Fast tests of single modules: FSRS, parsers, OCR, backup, difficulty, syllabus and others |
| `integration/` (45 files) | Real API calls against a temporary database: auth, privacy, tenant isolation, study flow, slides, jobs and others |
| `browser/` (14 files) | End-to-end tests in a real Chromium browser with Playwright |
| `js/` (6 files) | Frontend logic tests run by `npm test` |
| `fixtures/` | Sample lecture texts and expected answers the tests grade against |
| `conftest.py`, `helpers.py`, `__init__.py` | Shared test setup |

## 5. `scripts/`

| File | Use | Verdict |
|---|---|---|
| `dev/dev_start.py` | One-command local start (checks environment, launches app) | Keep |
| `dev/check_environment.py` | Checks Python, Ollama and models; used by dev_start and its test | Keep |
| `dev/run_tests.py` | Runs the full pytest suite | Keep |
| `dev/screenshots.py` | Regenerates README screenshots and the GIF | Keep |
| `dev/setup_assets.py` | Downloads model files into `models/` | Keep |
| `emotion/train.py` | Trains the camera emotion model | Keep (only needed to retrain) |
| `ops/backup_local.py` | Backs up your data to `backups/` | Keep |
| `ops/smoke_compose.py` | Docker smoke test CI runs | Keep |
| `eval/evaluate_retrieval.py`, `evaluate_grading.py`, `evaluate_ocr.py`, `benchmark_ollama_cpu.py`, `benchmark_embeddings.py`, `generate_eval_data.py` | Rerun the measurements behind `reports/` | Keep |
| `eval/live_study_journey.py`, `prepare_study_review.py`, `syllabus_matching.py`, `syllabus_checklist.html` | Study-quality and syllabus experiments | Keep |
| `eval/evidence_experiment.py`, `prepare_evidence_corpus.py` | Build and test the evidence corpus in `datasets/` | Keep (nothing links to `prepare_evidence_corpus.py`, but it is how `corpus.json` was made) |

## 6. `datasets/evidence_v1/`

| File | Use | Verdict |
|---|---|---|
| `corpus.json` | Frozen practice corpus for the evidence experiment | Keep |
| `manifest.json` | Hash and description of that corpus | Keep |

## 7. `docs/`

### Current guides and architecture: Keep
| File | Use |
|---|---|
| `README.md` | Index of all docs |
| `guides/SETUP.md` | Installing and running |
| `guides/STUDY_GUIDE.md` | How a student uses the app |
| `guides/EMOTION.md` | Camera feature: privacy and how to turn it on |
| `guides/AUTHOR_REVIEW.md` | Checklist for your own review and a student pilot |
| `architecture/ARCHITECTURE.md` | How the system fits together |
| `architecture/STUDY_RUNTIME.md` | How a study turn runs end to end |
| `architecture/OCR_DEPENDENCY_DECISION.md` | Why OCR is optional |
| `INTERVIEW_GUIDE.md` | Pitch and talking points for interviews |
| `project/PRD.md` | Product requirements |
| `project/ENGINEERING_RULES.md` | Rules every change follows |
| `project/CONTRIBUTIONS.md` | What you built versus the original project and AI help; important for honesty in a portfolio |
| `project/FEATURE_AUDIT_2026-11-06.md` | Latest audit: what works, what's untested |
| `project/phase-4-test-plan.md` | The manual check you're about to do |
| `project/plans/animation/*.md` (6) | Planned motion fixes not yet built |

### Evaluation write-ups: Keep (they back the numbers in README)
`evaluation/EVIDENCE_EXPERIMENT.md`, `LOCAL_GENERATION_EXPERIMENT.md`, `MODEL_COMPARISON_2026-10-29.md`, `STUDY_QUALITY_2026-10-12.md`, `FOLLOWUP_EVALUATIONS.md`.

### Out of date: Review
| File | Why |
|---|---|
| `project/tasks/plan.md`, `todo.md`, `continuation.md` | October "study overhaul" ledger, replaced by the feature audit. Still linked from `STUDY_RUNTIME.md`, `PRD.md`, `ENGINEERING_RULES.md` and `docs/README.md`. Move to `archive/` and update those links |
| `project/phase-4-slide-study.md` | Build contract for the Phase 4 agent team; Phase 4 is done |
| `project/HUMAN_HANDOFF.md` | 29 Oct handoff, replaced by the audit |
| `project/HIRING_READINESS.md` | 14 Oct remediation pass, finished |
| `project/PORTFOLIO_REPORT_DRAFT.md` | Draft report; keep if you'll finish it, otherwise archive |
| `project/DEVELOPMENT_LOG.md` | History log; harmless, keep if you like the record |

### Archive: Review
| File | Why |
|---|---|
| `archive/RELEASE_HANDOFF.md`, `archive/FIX_REPORT_2026-10-11.md` | Old but still linked from 9 and 1 files |
| `archive/PROJECT_ANALYSIS_2026-09-30.md` | Analysis of the original upstream code. **Nothing links to it.** Remove? |

### Images
| File | Use | Verdict |
|---|---|---|
| `images/journey.gif`, `study-light-1280.png`, `quiz-dark-1280.png`, `progress-dark-1280.png` | Shown in README | Keep |
| `images/flashcards-light-1280.png`, `library-light-1280.png`, `study-dark-1280.png`, `study-light-390.png`, `today-light-1280.png` | Made by `screenshots.py`, but **no doc shows them**, and they predate the dark redesign | Remove? (or add them to README) |

### Design
| File | Use | Verdict |
|---|---|---|
| `design/inspiration/*` (13 files) | Reference notes and logo drafts behind DESIGN.md | Keep |
| `design/mockups/sentio-dark-mockup.html`, `today-dark.png` | The approved dark redesign mockup | Keep |
| `design/mockups/compare-today.png`, `library-board-dark.png` | Comparison shots from the redesign; **not linked anywhere** | Remove? (small) |
| `design/mockups/.impeccable/config.json` | Design-checker settings for the mockup folder only | Remove? |

## 8. `reports/`

| File | Use | Verdict |
|---|---|---|
| `AI_EVALUATION_2026-10-11.md`, `GRADING_FOLLOWUP_…`, `OCR_EVALUATION_…`, `EDGE_CASE_AUDIT_2026-10-15.md` | Write-ups of measured results | Keep |
| `CPU_LATENCY_2026-10-11.md` | Latency write-up. Nothing links to it, but it explains `latency-2026-10-11.json` | Keep |
| `*.json` at the top level (evaluation, grading, latency, OCR) | Raw results behind those write-ups | Keep |
| `generation/*.json` (10) | Raw results for the model comparison and study-quality docs; `test_generation_compare.py` reads this folder | Keep |
| `evidence/status-v1.json` | Says the evidence corpus is waiting for human review | Keep |
| `verification/edge-recheck-20261015/*` (5) | Proof files behind the edge-case audit | Keep while you keep that audit |
| `archive/generation/*.json` (7) | Earlier runs (v1–v3) replaced by the current ones; only old docs mention them | Review: delete if you don't need the history |

---

## Summary

- **Must stay:** every file in `src/`, `tests/`, `scripts/`, the root config and `.github/`. Nothing there is dead.
- **Safe to delete (nothing links to them):** 5 unused screenshots in `docs/images/`, 2 mockup PNGs and the mockup `.impeccable/config.json`, and `docs/archive/PROJECT_ANALYSIS_2026-09-30.md`.
- **Worth archiving (out of date but still linked):** `docs/project/tasks/*`, `phase-4-slide-study.md`, `HUMAN_HANDOFF.md`, `HIRING_READINESS.md`, and possibly `reports/archive/`.
