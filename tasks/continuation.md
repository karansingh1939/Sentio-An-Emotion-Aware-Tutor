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
