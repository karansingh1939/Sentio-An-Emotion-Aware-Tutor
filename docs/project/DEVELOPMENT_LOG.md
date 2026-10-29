# Development record

## 2026-10-12 - Hiring-readiness repairs and real study stress tests

The first real Compose CI attempt exhausted the runner's disk after a successful
image build/CLI check. GitHub's worker crash prevented step logs and a Compose
artifact from being uploaded. Disabled retained uv caches in Docker layers and
selected copy linking before rerunning the unchanged smoke acceptance checks.
This is an image-footprint repair; the subsequent hosted result is required.

Cache removal alone did not resolve a second runner disk exhaustion. The locked
PyPI Linux PyTorch distribution pulled CUDA/triton libraries into a CPU retrieval
runtime. Selected the official CPU index for Linux with an explicit torch source,
retaining base version 2.14.0 and the Windows/macOS PyPI variants. Relocking removed
19 unnecessary CUDA/triton packages without upgrading other libraries. CI now
records image size and available disk before the Compose check. The official uv
source configuration is linked in SETUP.md; hosted Linux tests cover this variant.

The CPU image built at 1,815,328,309 bytes with 11 GiB free before starting
Compose. Startup then exposed a real configuration bug: production mode inherited
wildcard CORS and correctly refused to start. Reproduced this with the actual
production validator, configured the two local browser origins in Compose, and
retained the security guard. The new Compose configuration regression fails
before that fix and passes afterward. API logs are captured before test cleanup.

Added a commit/test contribution map and aligned the package, normal tutor
messages, and experimental camera wording with the supported study workspace.
Runtime tutoring now sends owned source passages and learner memory as JSON user
data, with exact citation references and source rules taking precedence over
examples. Legacy benchmark prompt construction remains unchanged.

Standalone numeric short answers compare exact fractions/decimals/percentages;
evaluation distinguishes these deterministic checks from model inference. Known
semantic errors remain documented, and the practice UI exposes that limitation.

Ran two real 12-case HTTP observations on longer synthetic fictional notes;
retained protocol failures and both model runs. The final run has no source
fallbacks but still refuses some answerable questions and mishandles ambiguity.
The updated lexical diagnostic passes 8/12, which is not semantic accuracy or
independent review. Prepared a private offline packet for the owner's actual
review; no human labels, model training, user adoption, or learning gains exist.

Compose adds independent health checks and loopback binding. Its isolated smoke
test uses disposable runtime mounts and no model downloads, checks saved work
and token continuity across restart, then stops Ollama to test saved browsing.
Hosted CI is required for actual container verification because Docker is
unavailable locally. See the hiring-readiness ledger for remaining evidence.

## 2026-10-12 - Publication on karansingh1939 and repository presentation

Published the current study-overhaul history to the verified owner's existing
private repository, `karansingh1939/Sentio-An-Emotion-Aware-Tutor`. Preserved the
other account's remote as `other-account-origin`; retained original attribution,
license, and the locally preserved legacy history. Only the current development
history was pushed, with no force push or historical LFS artifacts.

Reworked the README around supported capabilities, portable setup, architecture,
measured evaluations, and contribution boundaries. Added setup, contribution,
and security guidance, issue forms, and a PR template. Updated repository
description/topics. Extended CI with package builds, Compose validation, Docker
image build/CLI verification, concurrency cancellation, and timeouts. Excluded
scratch reports and backups from the Docker build context.

Local verification passed 240 tests and 31 subtests, with one optional Tesseract
test skipped, plus JavaScript, lint, formatting, and package builds. The first
hosted run passed the Docker job but exposed evidence-review file-input overflow
on Linux. Reproduced overflow locally at 320 pixels, constrained flex children
and the file control, and expanded the existing browser regression to 320/390
pixels. Both widths and the evidence dataset checks pass after the fix. The
follow-up hosted run is the authority for final Linux verification. Docker build
and CLI checks do not establish a full live Compose tutoring journey.

Historical publication entries below refer to the separate `karansingh-1939`
account; the requested current destination is `karansingh1939`.

## 2026-10-11 ? Working baseline

Problem: a partial package migration left build/test setup inconsistent and study
flows had persistence, grounding, privacy, and rendering failures.

Changes: completed the validated `src`/uv layout and repairs documented in
[the repair report](../archive/FIX_REPORT_2026-10-11.md). Preserved upstream history and MIT
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

## 2026-10-11 — Grading decision and real OCR evidence

Completed three repeats per grading profile: each passed 23/28 rubrics (20/25
semantic cases). The candidate removed two false positives but added two false
negatives per repeat; no production prompt change was adopted. A second targeted
context probe also retained failures. Raw results and readable decisions are
published in the grading follow-up report. Exact/blank checks remain separate.

Hosted Linux CI passed 152 tests and 31 subtests, including real Tesseract. The
synthetic OCR benchmark passed all nine cases, measured zero normalized word/
character errors on eight generated scans, and preserved native mixed-PDF text
and citations. Recorded the actual report with CI run provenance, engine/font
versions, hashes and per-case latency. These are synthetic observations, not
real-world accuracy claims. No learner data or model weights were published.

Next: obtain independently reviewed realistic OCR/grading labels and compare a
stronger suitable local grader before changing grading behavior. Docker execution
and emotion accuracy remain unverified. Keep repository visibility private.

## 2026-10-14 - Hiring-readiness completion pass

Compose startup/authentication/restart/provider-outage verification is now green
in hosted CI (run 38266463167); full model inference inside Compose remains a
separate validation. Fixed a reproducible UI race where closing the session
dialog before its POST response still activated the created session. The real
Chromium regression failed before the fix and passed afterwards, also verifying
that the unused session is persisted as inactive.

Full local regression: 258 passed, one optional Tesseract skip, 31 subtests passed.
JavaScript tests, formatting, Ruff and the dependency lock check passed.
Prepared 1,584 cached CPU evidence features and separate 12-answer and evidence
review pages. No human labels or independent reviewer results have been supplied;
training and adoption remain gated. The current human-only handoff separates
these actual human tasks from the wider product roadmap.
