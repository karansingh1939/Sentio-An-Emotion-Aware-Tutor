# Sentio product contract

A college student's free local study workspace, usable on CPU. Connect notes,
cited explanations, practice, revision and exam preparation. Demonstrate model
design and reliable AI engineering while preserving upstream attribution.

## Experience

Today: continuation, due work and goals. Library: owned material and previews.
Study: tutor and source evidence. Review: quizzes, cards and mistakes. Progress:
assessment evidence, goals and history. Settings holds privacy and diagnostics.
Light/dark themes, keyboard access, responsive layouts and honest error states
apply everywhere. Internal IDs are not normal product content.

## Architecture

FastAPI/Pydantic/Python 3.12, modular browser JavaScript, SQLite, Qdrant and Ollama.
One local process, no paid service or mandatory GPU. Preserve accounts, documents,
sessions, assessments and schedules. Additive APIs and transactional migrations.
Saved material works without AI. Camera is opt-in, experimental and lazy-loaded.

## Required behavior

- Owned bounded ingestion/generation jobs, progress, cancellation and retry.
- Readable streaming; final validation; incomplete turns never count as learning.
- Shared selected sources, valid owned citations and insufficient-evidence handling.
- Objective scoring, retryable semantic grading, editable cards, persistent reviews.
- Goals, target dates and budgets; deterministic revision queue.
- Recoverable replacement/deletion, backup/restore and upgrades.

## Model design

Train a CPU passage-support classifier against retrieval baselines. Document data,
frozen splits, validation-only tuning, calibration, ablations and held-out results.
Adopt only on measured benefit. Passage support is not answer truth or mastery.
AI-generated labels require manual review and are never independent ground truth.

## Acceptance

Upload → cited explanation → practice → review → restart without lost work.
Ownership, safe rendering and regressions pass. Browser layouts at 390/768/desktop
work in both themes. Report live AI quality/latency separately from fixture tests.
Deliver architecture, dataset/model cards, measured report, course/demo material
and honest résumé bullets. Public deployment and billing are out of scope.

See tasks/plan.md and tasks/todo.md for the approved sequence.
