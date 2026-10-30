# Continuation

Implementation started 12 October 2026 on feature/sentio-study-overhaul.
Initial tracked tree clean. Prior baseline: 151 Python tests + 31 subtests passed,
one optional OCR skip; all five JavaScript checks passed.

## Completed checkpoints

1. PRD/rules/ledger updated. Backup CLI snapshots SQLite, holds Qdrant lock,
   checks SHA-256, and rejects nonempty restore destinations and unsafe paths.
   Private snapshot: backups/pre-overhaul-2026-10-12. Isolated restore:
   backups/restore-check-2026-10-12. All 1514 files verified.
2. GET /api/v1/ready reports storage/AI/retrieval/OCR/camera separately.
   Camera weights and TensorFlow load on demand. Optional startup failures do
   not prevent storage/UI. Health probes no longer acquire another Qdrant owner.

## Verification

- Focused backup/readiness/runtime tests: 10 passed.
- Full Python/browser suite: 158 passed, 1 optional OCR skipped, 31 subtests passed.
- Fresh API import asserts TensorFlow absent from sys.modules.
- Ruff corrections and formatting applied to touched Python code.

## Next action

Shell and shared-state slice implemented: five destinations, contextual tools,
light/dark themes, legible controls, keyboard focus/labels, no core external asset
requests, Today with explicit partial errors and assessment wording. Session
creation now uses one path; resume verifies before replacing active context;
requests respect external cancellation and concurrent loading state.

Evidence: real Chromium offline checks pass for all nine existing screens at
390/768/1440 widths in both themes; page errors and external requests absent.
Screenshots inspected at tmp/workspace-preview (test-only accounts). Existing
browser study/ownership regressions: 3 passed. JS checks and Ruff pass.

Next: durable migration/job infrastructure, document previews/progress/recovery,
then streaming with cancellation and persisted deduplication. Finish remaining
source/session synchronization as the job and streaming clients migrate.

Never publish, expose secrets, replace learner data, invent labels/results or mark
unfinished milestones complete. Record actual verification here.

## Durable jobs and tutoring checkpoint

Versioned migrations add jobs, request IDs and recovery-operation inventory.
Practice jobs capture session/source context; one worker per lane and eight-item
queue. Owner-scoped status/Stop, terminal-state race protection, retention,
interrupted-job recovery and publication barriers are implemented. Privacy export
and deletion include the new records and cancel pending owned work.

Tutor POST event streams publish only the JSON text field. Local inference is
serialized; Stop closes upstream; disconnect cancels unpublished work. Strict final
schema validation precedes the transaction that stores the response and exchange
count. Repeated completed IDs replay without double counting. Saved turns restore
the transcript and conversation context. Source updates cancel stale turns; latest
resume revision prevents duplicate transcript rendering. Logout clears chat UI.

Evidence: full Python/browser regression 176 passed, 1 optional OCR skipped,
31 subtests passed. Six JavaScript checks, Ruff, Prettier and locked dependency
checks pass. Real browser observes a draft, final answer, and one turn after
refresh. Provider tests cover fragmented JSON escapes, invalid output, disconnect,
upstream Stop and inference-slot release. Migration rollback and queued-turn
cancellation are tested. Build performed for wheel/source distribution.

Next exact task: prepare document text/embeddings without overwriting current
records; publish files and SQL with a recovery journal; filter vector candidates
against current SQL chunk IDs; add asynchronous ingestion, owner-scoped previews,
progress/cancel/retry and interrupted replacement/deletion tests. Then finish
planning/review services and the offline ML experiment track. No model-quality
claims or trained-model adoption are justified yet.

## Library checkpoint

Uploads submit bounded ingestion jobs with progress, Stop, saved job IDs and
navigation/refresh recovery. Preview reads are paginated and owner scoped; source
text is escaped and dialogs support keyboard dismissal and focus restoration.
Search preserves input focus. Embedding/reranking models load from the local CPU
cache; absent models retain searchable keyword passages.

Prepared revisions use distinct vector IDs. Only committed SQL chunks can be
retrieved; text and citation metadata come from SQLite. File publication/deletion
use a recovery journal: failed SQL transactions restore old files, and committed
cleanup retries never restore superseded revisions. Limits: 20 MiB uploads,
2 million extracted characters and 2000 passages.

Focused recovery/API tests cover ownership, empty replacements, failed publication,
partial SQL writes, cancellation after vector staging, interrupted file moves,
cleanup retry, unsafe paths and malformed journals. Chromium checks upload,
preview escaping, keyboard focus, reload, second upload after tutoring and source
switching. A navigation race discovered by that journey was fixed.

Next: persistent daily budget/revision tasks, owner-scoped goal updates/completion,
paginated history and real planner/feedback services using saved-study evidence.
Then connected mistake review/card editing and versioned offline ML experiments.
Manual label review remains required before supervised results justify adoption.

Library checkpoint verification: 186 Python/browser tests passed, 1 optional OCR
test skipped, 31 subtests passed. All six JavaScript checks, Ruff, formatting,
lockfile checks and wheel/source packaging passed.

## Planning and history checkpoint

Migration 3 persists daily budgets and deterministic daily-plan snapshots. Due
cards precede weak areas and dated goals; at most six tasks fit a 5–240 minute
budget. Completion is explicitly self-reported, idempotent and owner scoped.
Existing snapshots preserve completed work when budget/preferences change.
Goal text/date/status updates persist. Today exposes these controls; browser
checks prove goals, budget and completion survive reload. Planner and feedback
nodes now read saved plans/practice records instead of sleeping stubs, including
attempt counts and an unassessed state. Planner previews do not publish side
effects during a cancellable turn. History uses bounded SQL pages and late-response
owner/route guards.

Verification: 189 Python/browser tests and 31 subtests passed; 1 optional OCR skip.
Six JS checks and Ruff passed. Next: saved quiz access, mistake review, flashcard
editing and atomic/deduplicated review publication; then tools/hardening and ML.

## Connected practice checkpoint

Saved quizzes are paginated and reopen without AI; submissions use the quiz's
original owned session. Review exposes recent mistakes alongside saved quizzes
and explanations. Flashcards can be edited during review and flipped by keyboard.
Card schedule, mastery update and request receipt now commit atomically; matching
rating retries replay and conflicting IDs return 409. A failed schedule write
rolls back mastery too. Privacy inventory includes rating receipts.

Browser journey now verifies upload, escaped preview, streaming answer, reload,
saved quiz, mistake review, card editing, keyboard flip and persisted review.
It exposed that normal reads exhausted the shared rate budget: reads/writes now
have separate bounded budgets, with retryable errors instead of false empty lists.
Student answers in quiz feedback are escaped; late job completions and auth
failures from a previous account cannot replace current account state.

Verification: 191 Python/browser tests, 31 subtests passed; 1 optional OCR skip.
All six JavaScript checks, Ruff/formatting and lockfile checks pass.
Next: preserve ingestion/practice submission IDs before sending, so an unknown
POST outcome can reconnect without duplicate jobs; finish hardening/tools and ML.

## Submission recovery checkpoint

Ingestion and practice retain a submission ID before their POST. Durable
owner-scoped receipts replay matching jobs, reject changed payloads with 409,
and return 410 for expired job records rather than duplicating completed work.
Library navigation reconnects an earlier upload before submitting a newly chosen
file. Browser regression deliberately restores the earlier completed receipt
and verifies the second file still uploads.

Verification: 193 Python/browser tests, 31 subtests passed; one optional OCR skip.
Six JavaScript checks passed. Next: persistent protected local signing keys,
storage-failure readiness, camera lifecycle and remaining hardening, then the
reviewable dataset and reproducible model experiments. Labels remain unreviewed.

## Local key and camera checkpoint

Generated development keys persist beside SQLite, are published only after
restricting file access, and are never written into global configuration.
Windows access is limited to the current user and SYSTEM; Unix uses mode 0600.
Corrupt keys fail with restore guidance. Explicit configured keys retain precedence.
Isolated backup/restore verifies an earlier token remains valid. SQL errors hide
query parameters. Storage readiness returns recovery guidance on a failed probe;
vector-store availability is separate from a loaded semantic encoder.

Camera startup checks current consent/owner/session and invalidates pending media
on navigation, logout or consent changes. Late grants and failed optional model
loading stop tracks. This exposed two legacy calls to nonexistent tracking-loop
functions; they now use the actual attention loop. Consent is off by default and
is no longer silently accepted if its modal is absent.

Verification: seven focused key/readiness tests; 17 identity/browser tests plus
31 subtests; all six JS checks including delayed media grants and model failure.
Next: atomic practice publication against source/session revisions, remaining
hardening and the reviewed-dataset/experiment track. No ML improvement is claimed.

## Practice publication checkpoint

Practice job fingerprints now include selected source checksums. Final quiz/card
publication checks the persisted owner, active session, subject/topic/difficulty,
selected sources and current document revisions inside the same SQLite write
transaction as artifact creation. Stale context, removed accounts or missing
decks cancel publication. Card prerequisites and card writes share the transaction.
The camera stop path also clears its telemetry timer and unsent buffer.

Verification: source-replacement and context-switch regressions pass for both
practice tools. Full suite: 199 passed, one optional OCR skip, 31 subtests passed.
Six JavaScript checks and Ruff pass. Next: authored corpus, frozen topic/source
splits, manual review workflow and reproducible CPU evidence-model experiments.

## Evidence experiment and review checkpoint

Frozen evidence_v1: 30 original AI-assisted academic drafts, ten topics,
120 questions and 1584 complete within-split passage pairs. Manifest hashes and
leakage checks keep sources, variant groups and near duplicates within splits.
All labels remain unreviewed. The CLI and offline browser page require reviewer
identity, rationale and a text-bound receipt, hide AI proposals, save progress,
support skip/import/download, and never create a label for uncertainty. The user
said they do not know how to review; the browser page now explains with examples.
Open reports/evidence/review-v1.html; start with ten decisions, without claiming
that the full label dataset is reviewed.

Implemented CPU extraction, training-standardized class-balanced logistic
regression, development-only regularization selection, separate calibration and
selection topics, threshold selection, retrieval/support/coverage/calibration
metrics, failure cases, bootstrap intervals and seven feature ablations. Reuses
existing BM25/hybrid/cross-encoder code. Optional MLflow stays outside startup.
Models are experiment artifacts, never automatically adopted. Production latency,
live grounding review and the adoption gate remain required.

Actual cached embedding collection succeeded. Cross-encoder weights are missing;
its comparison is explicitly unavailable and no download was performed.
reports/evidence/status-v1.json records hashes, installed versions, observed RSS
and one warm small-corpus pass: hybrid p95 about 11.1ms. This excludes model
loading, Qdrant and generation; it is not a production performance claim.

Verification: 207 tests passed, one optional OCR skip, 31 subtests passed; six
JavaScript checks pass. Full training/export mechanics pass only synthetic unit
fixtures. No real classifier or accuracy result exists before manual review.
Next: remaining hardening (bounded bodies/stable errors/recovery), tool exports,
live CPU generation comparison and release/showcase records; review is independent
of these tasks and must not be simulated by AI.

## HTTP boundary checkpoint

Request bodies are bounded before parsing/spooling: 2 MiB for ordinary requests,
24 MiB for multipart upload requests, with the existing 20 MiB file limit retained.
Actual chunked bytes are counted, not only declared Content-Length. Malformed
lengths and oversize JSON/multipart bodies return stable errors. Internal HTTP
500 details and unhandled SQL failures no longer expose private messages. Responses
disable content sniffing, referrer forwarding and framing. Authentication has its
own stricter budget; normal study reads/writes remain separate. Retry-After now
reflects token replenishment and is tested by retrying after the indicated wait.

Verification: 209 tests passed, one optional OCR skip, 31 subtests passed.
Next: recoverable account/file cleanup on failed deletion, bounded recovery
records, remaining tool/context guards and live-model release measurements.

## Account recovery and legacy storage checkpoint

Account SQL deletion and a cleanup inventory now commit together before any file
removal. Failed transactions preserve account/files and reopen the owner's job
queue. Interrupted filesystem/vector cleanup reports cleanup_pending and retries
at startup; records disappear only after cleanup succeeds. Paths and identities
are checked before deletion, active accounts cannot be cleaned, and other
learners' accounts remain intact. Recovery journals retain pending work while
terminal entries are bounded to seven days and 500 per owner.

Legacy synchronous quiz/card APIs now enforce the same final owner/source/session
publication transaction, preventing late generation from recreating deleted
account artifacts. Older in-process source fixtures now persist context just as
the real source endpoint does. Legacy schema bootstrap uses explicit transactional
DDL and schema inspection; actual ALTER failures propagate instead of being
silenced. Injected interruption tests prove fresh tables and upgrade columns roll
back, preserving previous rows, and upgrades remain idempotent.

Verification: 216 passed, one optional OCR skip, 31 subtests passed. Next: remaining
Windows library/context/tool checks and the installed-model CPU comparison, then
release documentation and validation. Label review remains pending; the user's
review page is ready with examples and saved progress.

## Grounding, tools and live CPU checkpoint

Selected notes without a relevance signal now produce an explicit insufficient-
evidence response without calling the model or falling back to curriculum.
Central teaching instructions require passage-based facts, clarification and
actual supporting references; final validation rejects unknown/missing citations.
This proves reference membership, not semantic support. The raw 0.35 cosine/term
overlap gate is uncalibrated and still needs coverage/unsupported-acceptance
evaluation. Offline raw-hybrid results must be brought into parity with this gate
before learned-model adoption. Stream history is rebuilt from matching persisted
source checksums, and the final write transaction rechecks document versions.

Jobs now persist their submission context (migration 7) and expose it in owned
status. GET /sessions/{id}/context supplies the current owned snapshot. Browser
practice completion is saved but not painted into a different context. Shared
token refresh and identity checks prevent late refresh/private JSON from replacing
a new account; transient refresh failure preserves authentication. Tutor session
and source lists distinguish failed reads and discard late responses.

Whiteboards use owner/session IDs, preserve loaded undo state and per-visit drafts,
handle touch/scaled pointer coordinates and retain unsaved work on errors. Save
checks account/session/board ownership inside the publication transaction.
PNG/PDF export validates bounded finite vectors, preserves highlight alpha and
uses text font size; export waits for a successful current save. Real browser
tests download a colored PNG and reload the saved drawing. Camera grants are
invalidated on context/consent changes; optional SDK/WASM/model URLs are local,
with no automatic CDN/model fetch. Assets and a physical-camera test are still
missing; backend consent enforcement remains open.

Windows case-only filename collisions now preserve existing notes. Recovery
rejects linked/junction learner paths. A SQLite process lease excludes another
API and offline backup while storage is owned. The lease exposed an existing
browser-test shutdown race; the test now joins its server and asserts shutdown,
without weakening ownership checks.

Generation comparison: reports/generation/compare-cpu-v1.json and
compare-grounding-v2.json retain 72 repeated CPU requests across two installed
models and two prompt policies. Both answered the unsupported ethanol question;
prompt-only grounding failed. Qwen is faster on these cases and is not adopted.
Legacy and grounding prompt hashes are regression-tested for reproducibility.
See docs/evaluation/LOCAL_GENERATION_EXPERIMENT.md for the table, commands and limitations.

Live journey v1 rejected an uncited answer. v2/v3 exposed a one-question request
returning five with invalid options. Exact-count schemas now constrain generation
and publication for quizzes/cards; a red/green regression rejects wrong counts.
Shared deterministic fixtures now honor requested batch size so interruption
tests reach their intended final publication guard. Providers reject output-limit
termination and have a 180-second generation deadline even for continuing chunks.
reports/archive/generation/live-journey-v4.json records a complete real HTTP journey:
upload, cited response, unsupported response, quiz/score, cards/review, preferences,
task completion, restart and saved-work/token recovery. This is one authored
mechanics run, not learning or model-quality validation. Earlier failures remain.
The journey uses isolated data, stops its own Windows child processes, and stores
failure logs only in ignored tmp, excluding credentials from published reports.

Verification: uv run pytest -q --tb=short --show-capture=no: 232 passed,
one optional OCR skip, 31 subtests passed (tmp/release-regression-final.log).
After moving drawing ownership SQL into its repository, 12 focused tool/ownership/
browser tests pass (tmp/whiteboard-final.log). npm test: six checks pass; Ruff,
Python/JS format checks, uv lock --check and wheel/source packaging pass.
Architecture/sequence diagrams and an honest course/résumé draft are in
docs/architecture/ARCHITECTURE.md and docs/project/PORTFOLIO_REPORT_DRAFT.md.

Next exact slice: bind an owned goal selection to the shared study context,
persist its identity/version in practice and stream snapshots, and test goal
changes during generation. Then finish practice provenance/quiz editing,
backend camera consent and privacy lifecycle, remaining recovery/log bounds,
held-out grounding/repeated live acceptance and release deliverables. Preserve
unchecked milestones until their full gates pass. User does not yet know how to
label: the guided reports/evidence/review-v1.html page is ready with examples,
small batches, Skip and export. Zero real evidence labels are reviewed; no real
classifier, calibration gain or adoption result may be claimed or synthesized.

## User-priority checkpoint: simpler workflow and account recovery

2026-10-12. User reports confusing workflow/unnecessary controls and missing
password recovery. Prioritized these before goal binding. Details and remaining
human/engineering tasks are in docs/archive/RELEASE_HANDOFF.md; beginner instructions
are in docs/guides/STUDY_GUIDE.md.

Implemented guided Today/Library/direct Study; shared practice context, three-item
batches, automatic first card deck, accessible card flips and four ratings; normal
camera/voice/telemetry controls removed. Upload stages/errors are readable, expected
input failures do not leak internal errors. Resumption persists and failed session
closure keeps the active session. Owned review receipts reconcile a committed grade
whose response was lost, with one grade write verified in Chromium.

Authentication now issues actual HS256 JWTs (previous SEN token was custom signed).
Migration 8 adds token versions and hashed single-use local recovery keys. Forgot
password rotates keys, revokes old access/refresh tokens and cancels pending jobs.
Existing users create a key in Settings using their current password. PBKDF2-SHA256
now uses 600,000 rounds; legacy 100,000-round hashes upgrade at successful login
without overwriting a concurrent reset or losing existing recovery keys.

Default install excludes TensorFlow; camera is an optional extra. Dev dependency
includes pypdfium2 to retain optional OCR structural test coverage. A first run
revealed an outdated Analytics label assertion; updated to Practice estimate and
asserted its learning limitation copy. No failed tests were disabled.

Final verification: 240 passed, 1 external-Tesseract skip, 31 subtests passed
(tmp/usability-final-tests.log, 133.96s). Six JavaScript checks, Python/JS format,
Ruff, uv lock, source/wheel builds pass. Wheel contains new fallback/recovery
modules and UI. uv audit: no known vulnerabilities/adverse statuses in 202
packages; npm audit: zero. Actual 390px novice/recovery journeys, lost-grade
response, offline 390/768/desktop light/dark workspace and export checks pass.

Before migration, a 1515-file private snapshot was verified and restored into an
isolated directory; paths in ignored tmp/usability-backup-record.txt. SQLite integrity
is ok; account/session/document/quiz/card counts match that snapshot. Docker absent;
container acceptance unverified. No public publication or model download occurred.

Real three-item live journey initially failed on uncited tutoring/invalid quiz
(live-journey-usability-3-v1.json). After integration, mechanics complete using
source_excerpt tutor + source_recall quiz, generated cards, review and restart
(live-journey-usability-3-fallback-v2.json). Honest fallbacks are not validated
teaching; semantically false answers with valid citations remain a release gate.

Workspace server was stopped idle to sync dependencies and restarted supervised
with `uv run python -m sentio --host 127.0.0.1 --port 8001`, exec session 46198,
PID 31308. One earlier detached launch was blocked by automatic policy; supervised
foreground launch succeeded. Startup diagnostics now use the actual readiness
endpoint, not obsolete unused-camera health warnings or a hardcoded port.

Next exact engineering slice: cancel/discard session-creation modal work after
close and test late completion, then bind owned goals into shared context; finish
practice provenance/quiz editing. Keep backend camera APIs excluded from supported
use until consent and image limits are hardened. Subsequent gates: reviewed labels,
MLflow tracing, held-out grounding, repeated live acceptance and student learning
validation. No real evidence labels are reviewed; no classifier gains are claimed.

## Completion pass - 14 October 2026

Fixed the session-creation modal race: a delayed POST response after closing the
dialog cannot activate a session, and the unused created session is closed while
the same owner remains signed in. The real Chromium regression failed before
the fix and passes afterwards, including the persisted inactive session assertion.
Full local suite: 258 passed, one optional Tesseract skip, 31 subtests passed.
JavaScript checks, Prettier, Ruff and locked dependency checks passed.

Prepared all 1,584 cached CPU evidence features and both local review pages:
reports/evidence/review-study-2026-10-14.html and
reports/evidence/review-evidence-2026-10-14.html. No human labels were invented.
docs/project/HUMAN_HANDOFF.md records the remaining author review, complete classifier
labels, actual students and independent review. Training/analysis can resume
when actual receipts arrive; wider roadmap gates remain unchanged.

## Edge-case repairs — 15 October 2026

Branch: codex/fix-audit-edge-cases. All four reproduced findings from
reports/EDGE_CASE_AUDIT_2026-10-15.md are fixed: selected documents always reach
retrieval/evidence validation; upload and sync share image extensions; full
stream buffers preserve completion/error/cancellation; successful recovery
operations trigger retention, including historical done records. Today remains
the revision-plan/progress entry point while selected-note chat stays grounded.

Regression cases failed before the changes. Focused modules: 47 passed. Full
Python/Chromium suite: 282 passed, 31 subtests passed, one Tesseract skip, one
existing TestClient timeout deprecation warning. All six JS scripts, Prettier,
Ruff lint/format, and offline wheel/source builds pass. An in-memory routing
mutation was rejected by six regression cases. Test socket/key restrictions were
resolved with permitted isolated execution; no tests or quality gates weakened.

Remaining: real OCR needs Tesseract, and live-model semantic quality, independent
human review and student-use acceptance still require their separate evidence.
The frontend agent's earlier interrupted audit was not exhaustive. No personal
documents/databases were changed. Resume the existing roadmap/human handoff;
the four audited bugs have no remaining implementation work in this branch.

Fresh evidence recheck requested by owner: 51 focused tests passed in 10.04s;
full Python/Chromium run passed 282 tests and 31 subtests in 159.46s, with one
missing-Tesseract skip and one existing TestClient deprecation warning. JS/lint/
formatting passed again. Reports, raw output, JUnit, source hashes, and read-only
synthetic database observations are saved under
reports/verification/edge-recheck-20261015/EVIDENCE.md. Application code and tests
were unchanged during the recheck. Live semantic quality and real OCR remain
separate validation limits.

## Backup rename lock — 29 October 2026

A full run on Windows failed once with WinError 5 when create_backup renamed its
verified staging folder; reruns passed. Backup and restore now retry that final
rename with short backoff on PermissionError (up to 8 attempts, about 6s) and
re-raise if the lock persists, leaving no partial snapshot. Two regressions
simulate transient and persistent locks; a real lock during one loop added an
extra attempt and the backup still succeeded. Backup tests: 20 consecutive
passes. Full Python/Chromium suite: 284 passed, 31 subtests passed, one
missing-Tesseract skip, one existing TestClient deprecation warning.

## Repository restructure — 29 October 2026

Owner-approved layout cleanup, no behaviour change. persistence/ merged into
repositories/ (documents, jobs, migrations, planning, practice, quizzes, sessions,
whiteboards); repeated suffixes dropped (quiz/service.py, flashcards/service.py,
whiteboard/service.py, intelligence/service.py and engine modules, auth/service.py,
session/manager.py, tutor/agent.py). Tests split into unit/integration/browser/js;
scripts into dev/ops/eval; docs into guides/architecture/evaluation/project/archive
with tasks under docs/project/tasks; superseded raw runs in reports/archive/.
Readme.md is README.md. Removed the duplicate tests/run_isolated_tests.py and
scripts/profile_sentio_performance.py (undeclared pyinstrument dependency).
generate_eval_data.py and benchmark_embeddings.py now accept --help instead of
writing files. Working-tree line endings normalized to LF. Local clutter (tmp,
graphify-out, caches, old test DBs and log snapshots) deleted; personal data,
models and backups kept, with tmp keepers moved to backups/preserved-from-tmp-2026-10-29.
Checks: 284 passed, 31 subtests passed, one Tesseract skip; JS, Prettier, Ruff,
offline wheel/sdist build, all scripts' --help, all Markdown links, and app startup
(/api/v1/ready, /, /docs) pass.

## Quality and study features - 29 October 2026

Branch: feature/quality-and-study-features. Item 1: live_study_journey.py gained
--model; four installed models ran the 12-case grounding test
(docs/evaluation/MODEL_COMPARISON_2026-10-29.md). qwen2.5:7b and llama3 answered 3/4
covered questions vs 2/4 for phi3:mini, all declined 6/6 absent facts; qwen2.5:7b
is recommended where memory allows. Default stays phi3:mini pending the owner's
choice and author review. Item 2: sessions bind an owned active goal (part of the
study context version; tutor sees it); saved quizzes and cards store provenance
(mode, model, cited pages, note checksums); owners edit quiz questions with revision
checks so earlier submissions replay unchanged (migration 9). Item 3 prepared:
reports/evidence/review-study-2026-10-29-qwen2.5-7b.html (ignored, private) awaits
the owner's review. New API, integration and Chromium regressions cover all three.

Quiz repair follow-up, 29 October 2026: qwen2.5:7b quizzes fell back to source
recall because schema mismatches were reported as provider unavailability, skipping
the parser's repair/regeneration, and the model omitted true/false options. Added
InvalidModelOutput, routed practice mismatches through repair/regeneration, and
filled fixed true/false options. Two live journeys then generated quizzes with the
model. The owner's .env now selects qwen2.5:7b (previous copy in backups/).

## Résumé simplification - 29 October 2026

Branch: refactor/resume-simplification (owner-approved plan). Removed the hidden
whiteboard, the OpenAI/Hugging Face backends and the JSON-file storage fallback
(legacy whiteboard rows are still deleted with an account). The LangGraph workflow is
now memory_lookup -> retrieve -> (refuse | generate). Emotion detection moved into
sentio/emotion as an opt-in side feature (ENABLE_EMOTION, server-checked consent,
bounded frames) with its browser code in static/js/core/emotion_camera.js. The UI
gained shared component classes, a study context bar, progress stat cards and a
screenshot/GIF tool (scripts/dev/screenshots.py). README and docs/INTERVIEW_GUIDE.md
were rewritten for the résumé. Full suite: 288 passed, 31 subtests, one Tesseract skip
(one run took 68 min because the machine had about 1.4 GB free memory).

## Easier study workflow - 29 October 2026

Branch: feature/easier-study-workflow. Library Study starts a session in one click
(topic from the notes' opening line, subject `general` now allowed). Retrieval emits a
`sources` event before the answer; citations render as chips that open the passage
(the hidden drawer citation panel was removed). Quiz questions can be checked
instantly via POST /quizzes/{id}/questions/{qid}/check, which reuses the extracted
QuizService.grade_answer and records nothing. Document overviews are generated as a
job (POST /documents/{id}/overview/jobs), cached in documents.overview_json against the
checksum. generate_structured now serves quizzes, flashcards and overviews. A
retrieval fallback for unmatched practice topics was tried and reverted: it mislabelled
unrelated topics.

## FSRS scheduler - 29 October 2026

Branch: feature/fsrs-scheduler. SM-2 was replaced by FSRS-5 (default parameters) in
src/sentio/flashcards/fsrs.py. flashcards gained stability, difficulty and
last_review_at columns (conditional ALTERs); ease_factor is kept only for converting
older cards. Due cards include next_intervals, shown under each rating button. The
learner model's forgetting risk and flashcard mastery evidence now use FSRS recall
probability. Parameters are not yet fitted on the learner's own reviews.

## Confirmed-bug fixes - 30 October 2026

Branch: fix/confirmed-bugs, from a three-agent feature review (advocate, critic, judge;
reports in tmp/feature-debate, not committed). Fixed: answers no longer read aloud
automatically; "Search all my notes" searches every subject; stream, cancel, grounding,
goal and telemetry requests go through sentioAPI (token refresh; `stream: true` keeps the
caller's abort signal); Start dialog defaults to "Search all my notes" when notes exist;
the session "×" now honestly ends (not deletes) active sessions; study streak counts
consecutive days; quiz summary is deterministic (no model call); short-answer Check
answer waits 190 s; EMOTION.md and INTERVIEW_GUIDE.md corrected. Not done: the judge's
removals and simplifications (adaptive difficulty, voice code, dead endpoints).

## Phase 1: notes-first study - 30 October 2026

Branch: feature/notes-first (stacked on fix/confirmed-bugs). Added courses (table
`courses`, `documents.course_id`; API under /courses and PATCH /documents/{id}/course),
PPTX ingestion (`python-pptx`, one page per slide), multi-file upload in Library, and
course sessions (`course:<id>`, resolved by `expand_source` at question time). Removed the
subject list and /subjects, the "General questions (without notes)" mode, and the
built-in curriculum (knowledge_base.py 1,208 -> 516 lines); quizzes and flashcards now
require notes, and old `none` sessions get a "choose notes" reply. The tutor prompt keeps
its CURRICULUM REFERENCE header so saved evaluation prompt hashes stay reproducible.
Next: Phase 2 (topic maps, per-topic mastery, weak parts).

## Phase 2: topics and mastery - 30 October 2026

Branch: feature/topic-mastery (stacked on feature/notes-first). Topic maps per lecture
(`note_topics`, deterministic from slide titles / page headings, checksum-invalidated,
rename and merge-up). Questions get `source_document_id`/`source_page` by word overlap with
retrieved passages (citations now include `document_id`); `quiz_attempts.question_id` links
answers. GET /documents/{id}/topics, GET /courses/{id}/progress, PATCH /topics/{id},
POST /topics/{id}/merge. Library shows course progress, a Progress-by-topic panel with
weak topics and Review/Practise buttons, and a Topics dialog per lecture. Quiz subject is
optional now. Not done: flashcards in the Ready rule; adaptive-difficulty rework (2b).

## Phase 2b: fair difficulty - 30 October 2026

Branch: feature/fair-difficulty (stacked on feature/topic-mastery). One policy in
`tutor/difficulty.py`: explicit requests (phrase regexes with false-positive tests) and
quiz streaks only; learner-model override and emotion-driven changes removed;
ContentAdapter.adapt_difficulty deleted. Pinning via POST /sessions/{id}/difficulty;
`difficulty_change` on stream and quiz results; tutor and quiz pages show the change with
Undo. EMOTION.md is "tone only" again, now true.

## Phase 3: syllabus progress - 30 October 2026

Branch: feature/syllabus-progress (stacked on feature/fair-difficulty). Syllabus per course
(`syllabus_items`; PUT/GET/DELETE /courses/{id}/syllabus with text or a PDF/DOCX/PPTX/TXT
file; PATCH /syllabus/{item} with mode auto/manual/none). Deterministic parsing (units,
comma lists, bullets, hours, skipped textbook/reference/outcome sections; a named unit
without a list is one topic). Live word-overlap matching to lecture topics (title x2, slide
text x1, threshold 0.5, up to 3). Status from topic states; percent ready. Library course
panel shows the syllabus, gaps ("Not in your notes yet"), match correction and Practise.
Next: Phase 4 (camera mode switch on the study page).

## Exact topic practice - 30 October 2026

Branch: feature/topic-practice (stacked on feature/syllabus-progress). Sessions carry
`topic_ids` (max 5, owner and source checked, in the study snapshot, cleared when the notes
change). `KnowledgeBase.topic_content` builds quiz context from the topics' own pages;
`study/topics.py` `fit_pages` caps it and `locate` places questions (named Citation Index
if checked, then word overlap, then the assigned topic). Multi-topic quizzes take turns.
`provenance.topics` and `provenance.located` record what happened; the quiz header shows
"From: ...". Topic ids are now deterministic: two concurrent builds used to give the page
ids that no longer existed. Fixed `npm test`, which had stopped at stale test stubs since
Phase 2. Next: Ready fades with FSRS (`tmp/plans/improvements-topic-practice-memory-matching.md`).
