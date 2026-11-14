# User edge-case audit — 15 October 2026

What this repo does: Sentio is a local study workspace for uploaded notes, source-based tutoring, practice and scheduled review. This audit assumes the documented local installation with one API process, including concurrent browser requests and background jobs.

The audit covered frontend flows, backend documents and persistence, and tutor and recovery paths. The frontend pass was not completed. Each of the four findings below was reproduced with a probe before it was recorded. The original audit changed no application code; the repair follow-up is recorded here.

## Repair follow-up — all four findings fixed

Changes are on branch `codex/fix-audit-edge-cases`.

Fresh recheck: all four fixes passed again, with 51 focused checks and a full run
of 282 tests plus 31 subtests passing. See the [evidence report](verification/edge-recheck-20261015/EVIDENCE.md)
for saved logs, JUnit results and read-only observations from the synthetic test databases.

| Finding | Result |
| --- | --- |
| 1. Selected-source routing | Selecting one document, several documents or all documents forces retrieval and evidence checks before answering. Planning/feedback keywords use whole-word matches in general study, so `planetary` no longer matches `plan`. Today remains the place for revision plans and progress while studying selected notes. |
| 2. Image rescan deletion | Upload validation and rescan share their supported extensions. Existing images are counted as present even when OCR is unavailable; failed re-extraction preserves the saved document and chunks. |
| 3. Stream termination | Terminal events can displace a queued draft event when the bounded buffer is full. Cancellation, provider errors and successful saved responses all reach the consumer; a completed response is not reclassified as cancelled because its final event encountered a full buffer. |
| 4. Recovery retention | New successful operations use `completed` and immediately run retention. Existing `done` rows are included in retention alongside completed/failed records; pending recovery stays intact. |

Verification:

- Added regression cases before changing production code: 20 failures demonstrated the reported bugs and routing false positive, with five preservation/control cases passing.
- Four focused test modules: **47 passed** after the fixes.
- Full Python suite including Chromium: **282 passed, 31 subtests passed, 1 skipped** in 160.43 seconds. One existing Starlette TestClient timeout deprecation warning remains.
- The skip is the real Tesseract image test because the executable is not installed. Synthetic OCR failures and saved-image preservation pass.
- All six JavaScript scripts, Prettier, Ruff lint, and Python formatting pass. Source and wheel builds succeed offline with the installed build backend.
- Inverted the selected-source routing guard in memory and reran its regressions: six cases failed as expected. No application file was changed for this mutation check.
- Tests used `SENTIO_HOME` pointing at a synthetic workspace directory, isolated temporary databases, and deterministic model providers. No tests were disabled.

The following entries retain the original reproduction details. They are no longer open bugs in this working tree.

Remaining limits: no live local-model quality/latency evaluation was run, and no guarantee of semantic correctness follows from checking citation references. Real Tesseract OCR needs its external executable. The frontend audit was not exhaustive; passing browser regressions does not establish that every user edge case has been found. Personal documents/databases were not modified, and these code changes do not automatically repair any records removed before the fix.

## Must fix

1. **Selected notes can be ignored because a topic contains a routing keyword (P1).**
   - What this is: `src/sentio/tutor/orchestrator.py:341` chooses which helper handles a tutor question.
   - Problem: With a document selected, ask “Summarize the planetary system in my selected notes”. The substring `plan` in `planetary` sends the request through `memory_lookup -> planner -> tutor`, skipping source retrieval. The isolated probe confirmed that the provider receives an empty `source_passages` list and its uncited answer is accepted. The insufficient-evidence guard at line 412 does not catch absent retrieval because it defaults to general context.
   - Fix: Separate explicit planning/feedback requests from source questions; require source retrieval and evidence validation for questions about selected documents. Whole-word matching also prevents `planetary` matching `plan`, but does not by itself solve document questions containing “review”.
   - If we skip it: A learner can receive an answer that appears to concern selected notes but was produced without reading them.
   - Evidence: `tmp/tutor_edge_probe.py`, output `SELECTED_SOURCE`, with a stub provider and retrieval configured to fail if invoked. This proves routing and acceptance behavior, not real-model answer quality.

2. **Library rescan removes uploaded images from the library (P1).**
   - What this is: `src/sentio/ingestion/pipeline.py:379` scans the document folders; line 392 starts pruning records absent from the scan. The administrative API at `src/sentio/api/routes/documents.py:280` exposes this operation.
   - Problem: Uploads accept PNG/JPG/JPEG at `documents.py:100`, but rescan enumerates only TXT/PDF/DOCX. An existing image is omitted and its database record and vector entries are deleted even while its file still exists.
   - Fix: Use the same supported-extension list for upload and rescan. Existing supported files must be counted as present even when optional OCR is unavailable.
   - If we skip it: Running an administrative sync makes scanned notes disappear from the library and retrieval. The original file remains on disk, but its registered study content is removed.
   - Evidence: `tmp/data_edge_probe.py` invoked the real scan method with a temporary image and recording storage doubles. Result: `deleted_count=1`, both deletion methods called, original image still present.

3. **A full answer buffer loses its stop event and leaves the stream open (P2).**
   - What this is: `src/sentio/tutor/stream_service.py:86` queues tutor events; `src/sentio/api/routes/streaming.py:58` sends them to the browser.
   - Problem: The queue holds 256 events. If a producer fills it before the consumer catches up, `emit` raises cancellation. The cancellation handler tries to put its final event into the same full queue, so it fails too. The finish callback does not repair a nonempty queue. After the browser drains the deltas, the HTTP loop keeps waiting because it exits only after a terminal event or disconnect.
   - Fix: Guarantee space or a separate signal for completion/error/cancellation, and let the response loop detect a finished worker even if its terminal event was lost.
   - If we skip it: A bursty producer or stalled consumer can leave a partial answer in a waiting state until the client times out, disconnects or retries.
   - Evidence: `tmp/tutor_edge_probe.py` emitted 300 deltas without consuming. Output: 256 queued events, no terminal events, no active worker, database request status `failed`. This deterministically exercises backpressure; it does not measure how frequently a live provider causes it.

## Should fix

4. **Successful document recovery records are never pruned (P3).**
   - What this is: `src/sentio/ingestion/recovery.py:85` applies retention to the journal of document changes.
   - Problem: Successful cleanup writes status `done` at line 202, while both retention queries select only `completed` and `failed`. Successful operations therefore escape the seven-day and 500-per-owner limits.
   - Fix: Use the same success status in cleanup and retention, accounting for existing `done` records.
   - If we skip it: Normal uploads, replacements and deletions keep adding journal rows and increase database/backup size over time. Immediate document corruption was not demonstrated.
   - Evidence: `tmp/data_edge_probe.py` used real SQLite and the real prune method. An old `failed` row was removed while an equally old `done` row remained.

## Verification and limits

- `npm test`: all six JavaScript test scripts passed.
- Both isolated probe scripts passed their reproduction assertions.
- A complete Python run was not obtained during the original audit: the environment it ran in could not use the default temporary directory, and publishing the local signing key failed with `PermissionError` at `os.link` in `auth/local_secret.py:48`. These environmental failures are not counted as application findings. The repair follow-up above records the later full run.
- A follow-up run of four relevant Python test modules with a synthetic signing key started but did not finish within this audit; it was stopped and is not reported as passing.
- The frontend pass produced no complete report. The passing JavaScript checks are not exhaustive coverage of navigation, accessibility, mobile layouts or stale state.
- No production deployment, personal-document testing, live-provider quality evaluation or destructive real-data tests were performed. Probes use synthetic data, temporary storage and explicit doubles.

Verdict: Fix source-routing correctness and image rescan deletion first, then stream termination. The four reproductions should become regression tests when fixes are implemented.
