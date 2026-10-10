# Development record

## 2026-10-11 ? Working baseline

Problem: a partial package migration left build/test setup inconsistent and study
flows had persistence, grounding, privacy, and rendering failures.

Changes: completed the validated `src`/uv layout and repairs documented in
[the repair report](FIX_REPORT_2026-10-11.md). Preserved upstream history and MIT
attribution. Learner data, credentials, model weights, and generated output remain
excluded from new commits.

Evidence: 131 Python tests plus 31 subtests, four JavaScript scripts, clean Ruff
and Prettier checks, successful wheel/source build, and a real local Ollama chat.
Docker, hosted CI, and a physical webcam were not verified.

Publication: intended private repository is
`karansingh-1939/Sentio-An-Emotion-Aware-Tutor`. Account authentication is required
before creation/push. The cached Git credential belongs to `karansingh1939`, a
different account; it will not be used to publish to the requested destination.

Next: replace simulated retrieval scores with a versioned isolated benchmark.

## 2026-10-11 ? AI evaluation and response workflow

Changed: replaced fabricated retrieval scores with a registered/authenticated
owner, isolated database, selected source IDs and real hit/Recall@5/MRR/latency
metrics. Added corpus v1.0 with answerable, paraphrased, negative and adversarial
cases, reference answers and grading rubrics. Kept exact matches separate.
Student grading text is now user data; blank answers reject without model calls.
The CPU benchmark uses fresh equivalent prompts, cold/warm separation and three
repetitions. Chat exposes generation state, deadlines and duplicate-send guard.

Evidence: isolated ownership, ranking, grading-boundary, equivalent-prompt and
JavaScript deadline regressions pass. Measured reports and raw results are
committed separately from implementation. Hybrid did not outperform keywords;
one valid semantic answer still failed. All three speed experiments lost measured
rubric quality, so production generation parameters remain unchanged.

Next: independent semantic labels, longer multi-passage sources, and quiet-machine
latency trials. Emotion accuracy remains unverified without labelled data.

## 2026-10-11 ? Optional OCR

Changed: optional PDFium extra and local Tesseract extraction, native-text
preservation, PNG/JPEG support, rotation selection, 20 scanned-page/20 MiB limits,
page citations, persisted text/OCR/mixed provenance and actionable errors.
Document Library exposes availability and extraction method. CI includes OCR tools;
Docker has an opt-in OCR build argument.

Evidence: fixture tests cover native, scanned/mixed, rotated, empty, encrypted,
oversized, missing-tool and replacement/provenance behavior. PDFium actually
renders in fixture tests; recognition calls are controlled fixtures. The live
Tesseract smoke test is skipped locally because its installation was canceled.
Docker and hosted GitHub Actions remain unverified.

Next: install the local OCR engine when available, then run the live smoke test
and evaluate recognition against labelled scans. Publishing remains private-only
and requires authentication as the exact requested GitHub account.

## 2026-10-11 ? Validation and publication attempt

Final local validation: 147 Python tests and 31 subtests passed, one live
Tesseract test skipped; all five JavaScript checks, Ruff, Prettier, and wheel/source
build passed. Browser regressions run in the Python suite.

GitHub device authentication succeeded and the authenticated API confirmed
`karansingh-1939`. Created and verified private repository
https://github.com/karansingh-1939/Sentio-An-Emotion-Aware-Tutor . Preserved the
old remote as `previous-origin`, retained `upstream`, and pointed `origin` at
the requested repository.

The baseline push was rejected with GH008 because preserved commits reference
24 unavailable Git LFS objects (old emotion checkpoints, a model and FER2013).
Those historical artifacts total approximately 1.6 GB. They are not included
in the current tree. GitHub requires them even though new commits exclude
weights and training data. No history rewrite or exclusion bypass was performed.
The destination is still empty and Actions cannot run until publication is
resolved. A user decision is required between allowing recoverable legacy LFS
objects, keeping publication blocked, or authorizing a separate clean history.

## 2026-10-11 — Authorized clean publication

The owner authorized the recommended clean publishing history. Original history
through `52455cc2` is retained locally on `preserved-original-history-2026-10-11`.
A separate baseline snapshot and the four completed milestone commits retain
MIT attribution and actual development dates. Six legacy generated document
fixtures are omitted; all other published blobs match the tested snapshot before
this documentation update. Original weights/training data and learner uploads
are excluded. Versioned evaluation fixtures and reviewed reports remain included.
The repository remains private. Publication and hosted CI verification follow.

## 2026-10-11 — Private publication verified

Published clean `main` at `49539f72` to the owner's private repository. Verified
the remote tree and exact LICENSE/README blob hashes; no weights, learner
uploads, databases or logs are present. Local `main` now tracks `origin/main`.
Original commits remain on `preserved-original-history-2026-10-11` and
`legacy-main-2026-10-11`; previous-origin/upstream and local generated documents
are preserved. No historical LFS objects were uploaded.

The clean checkout passed 147 Python tests and 31 subtests, with one optional
local Tesseract test skipped. JavaScript, Ruff and Prettier checks passed.
Hosted Linux CI passed with Tesseract installed:
https://github.com/karansingh-1939/Sentio-An-Emotion-Aware-Tutor/actions/runs/38083574712

Next: evaluate OCR against labelled scans, improve the documented semantic
grading false negative, and expand the retrieval dataset before proposing
performance changes. Emotion accuracy and Docker execution remain unverified;
keep the repository private until an explicit visibility review.

## 2026-10-11 — Repeated grading and labelled OCR evaluation tools

Added a 28-case versioned grading dataset and a three-repeat comparison with
alternating profile order, model digest and raw scores. Exact and blank answers
are now distinguished from semantic inference. Added real OCR measurements on
nine temporary synthetic fixture cases, including rotations and mixed PDF text.
Word/character edit rates and extraction provenance are recorded; native text
must remain exact. CI runs Tesseract and uploads the measured report.

Focused metric/category tests failed before implementation and passed afterwards.
Full local regression: 151 passed, one optional Tesseract test skipped, 31 subtests
passed. JavaScript, Ruff and Prettier checks passed. No production grading prompt
has been changed from this experiment. Next: inspect hosted OCR results and
publish the completed grading analysis with its unsuccessful candidate.
