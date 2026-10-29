# Fresh verification of the four edge-case fixes

Date: 15 October 2026, Asia/Calcutta. This is a new run after the repairs, not a copy of the earlier audit result. Application code and tests were not changed for this recheck.

## Direct evidence for each issue

| Issue | What was exercised | Observed result | Evidence |
| --- | --- | --- | --- |
| Selected notes bypassed source checks | Nine graph-execution cases combine the original planetary/review/goals triggers with one selected document, multiple documents, and all documents. A separate API test submits an unsupported question with a selected uploaded note. | All nine cases call retrieval with the selected documents. Missing evidence returns through the evidence gate without calling generation. The API test returns the missing-evidence response without calling its deliberately forbidden provider. General-study planning/feedback controls also pass. | [Named test results](focused.log); `tests/test_study_prompt_boundaries.py:62`, `tests/test_grounding_contract.py:51`. |
| Sync removed uploaded images | PNG, JPG, JPEG and uppercase PNG already indexed; rescan first with unchanged files, then modified files while OCR deliberately fails. | All four retain their indexed document and original saved text. Unchanged files are skipped; failed re-extraction does not delete registered documents, chunks or document vectors. | [Named test results](focused.log); [persisted image rows](database-state.json); `tests/test_ingestion_resilience.py:97`. |
| A full stream buffer lost the final event | Deliberately fill the actual 256-event queue before successful completion, cancellation, or a provider error; let the worker finish before consuming events. | All three deliver the expected terminal event. Success saves exactly one exchange and one completed turn. Cancellation and error save zero exchanges and no completed turn. Job statuses are succeeded/cancelled/failed respectively. | [Named test results](focused.log); [persisted stream rows](database-state.json); `tests/test_streaming_turns.py:158`. |
| Successful recovery journals grew indefinitely | Insert 510 recent successes plus an expired success and an old pending operation; exercise both current `completed` and historical `done` states. Exercise actual successful cleanup to check that retention runs. | Each run retains 500 terminal records and one pending record. The expired success is absent. Successful cleanup invokes retention. | [Named test results](focused.log); [persisted journal counts](database-state.json); `tests/test_document_recovery.py:33` and `:78`. |

The saved database observations were collected read-only from the synthetic test databases after the focused run. A cancelled stream request is stored as `failed` in `chat_requests`; its worker job is `cancelled`, and the emitted event is `cancelled`. It is never counted as a completed learning exchange.

## Test results and raw artifacts

- Focused regression/integration run: **51 passed in 10.04 seconds**. [Full output](focused.log), [JUnit results](focused.xml).
- Full Python/Chromium run: **282 passed, 31 subtests passed, 1 skipped in 159.46 seconds**. [Full output](full-suite.log), [JUnit results](full-suite.xml). The skipped test is real Tesseract OCR because the executable is not installed. One existing Starlette TestClient timeout deprecation warning remains.
- JUnit counts the 31 subtests separately, so its full-suite total is 314: 282 passed tests + 31 passed subtests + 1 skipped test, with zero failures and zero errors.
- All six JavaScript test scripts passed. [Output](javascript.log).
- Ruff lint, Python formatting and Prettier passed. [Lint](lint.log), [Python formatting](python-format.log), [JavaScript formatting](javascript-format.log).
- [SHA-256 hashes](source-hashes.json) identify the exact implementation and regression files checked.

The full command is `python -m pytest -q -rs --basetemp=tmp/edge-recheck-full-01 --tb=short --junitxml=reports/verification/edge-recheck-20261015/full-suite.xml`, using the repository's Python 3.12 virtual environment. The focused command substitutes the five modules listed in focused.log and uses `-vv`. Both set `SENTIO_HOME` to a synthetic directory under `tmp` and run with permission for protected local signing keys and localhost test sockets.

## What this evidence does not establish

- These tests establish source routing, evidence refusal, data preservation, stream termination and journal retention. They do not prove the semantic correctness of live AI answers.
- Image extraction is injected in the image-preservation regressions, and OCR failure is deliberate. Actual Tesseract OCR is a separate external-capability test; saved extracted text is the data being protected here.
- Model providers and vectors are deterministic fixtures/doubles where appropriate. Browser tests exercise real Chromium and the local API; they do not use personal documents or measure real-model answer quality.
- No claim of exhaustive discovery of every possible user edge case is made. This recheck covers the four reported issues and the existing regression suite.
