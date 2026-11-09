# Sentio study overhaul

Approved 12 October 2026. Build a free CPU-compatible local study product and an
honest AI/ML portfolio. Preserve existing learner data and upstream attribution.

## Product and architecture

Notes → cited tutoring → practice → weak-area review → exam planning. Navigation:
Today, Library, Study, Review, Progress; settings and diagnostics are secondary.
Calm light/dark themes, keyboard access, responsive layouts and offline essential
assets. Camera is opt-in, experimental and loaded on demand.

Browser → authenticated FastAPI → coordinator → services → repositories.
SQLite stores accounts, sessions, practice, goals, jobs and versioned migrations.
Qdrant and local files store retrieval material. Ollama supplies streamed local
generation. One application process owns Qdrant; one AI and one ingestion job run
at once. Optional MLflow is outside normal startup. Retain Python 3.12, Pydantic,
modular browser JavaScript and compatible locked stable dependencies.

## Model design

Predict passage support, not answer truth. Standardized class-balanced logistic
regression uses similarity, keyword relevance, overlap, lengths, rank and score
gaps. Calibration and threshold tuning use development data only. Corpus:
>=30 documents, 10 topics, >=120 questions; topic/document-disjoint 6/2/2 splits.
Record provenance and label rationale. AI-drafted labels remain unreviewed until
manual review; never call them independent ground truth.

Compare keyword, dense, hybrid, pretrained cross-encoder and learned gating.
Report Recall@5, MRR, nDCG@5, support precision/recall, unsupported acceptance,
answerable coverage, Brier score, reliability plots, latency, memory, ablations,
uncertainty and failures. Freeze test data and validation-selected thresholds.
Adopt only if unsupported acceptance decreases without reduced answerable
coverage and retrieval remains under 300ms; otherwise retain the baseline.
Keep phi3:mini until an officially documented CPU candidate passes measurements.
No automatic model downloads, paid inference, mandatory GPU or public publishing.

## Verification and delivery

Baseline: 151 Python tests + 31 subtests, 1 optional OCR skip; JS checks pass.
Focused regressions per slice, full checks at checkpoints. Real browser tests:
both themes and 390/768/desktop layouts. Separate fixtures from live AI quality,
camera accuracy and learning-effectiveness claims. Test ownership, interruptions,
stale requests, retries, migrations and restore. Deliver architecture, cards,
training/evaluation commands, measured report, demo, attribution and résumé
bullets containing actual results only.

Tasks: [todo.md](todo.md). Resume: [continuation.md](continuation.md).


### User-priority adjustment, 2026-10-12

First make the normal flow understandable: Today ? upload ? direct Study ?
shared-context quiz/cards ? review. Add safe local recovery, real JWTs, preserve
saved work and test the novice path. This checkpoint is implemented and measured
in continuation.md. Source fallbacks keep provider failures explicit. Remaining
milestones retain their original acceptance gates; see RELEASE_HANDOFF.md.
