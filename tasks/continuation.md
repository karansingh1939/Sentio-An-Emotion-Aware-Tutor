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
