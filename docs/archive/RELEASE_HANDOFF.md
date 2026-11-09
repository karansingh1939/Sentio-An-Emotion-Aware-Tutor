# Release handoff: usability checkpoint

Update, 14 October 2026: the closed-dialog session race is fixed and verified in
Chromium. The full local suite passes 258 tests and 31 subtests, with one optional
Tesseract skip. Cached CPU features and both review pages are ready. Use
[the current human-only handoff](HUMAN_HANDOFF.md) for remaining owner actions;
the instructions below describe the historical checkpoint.

Update, 12 October 2026: repository presentation, contribution mapping, runtime
prompt boundaries, deterministic numeric grading, and a recorded 12-case HTTP
grounding stress test are implemented. Compose image/startup/authentication/
restart/outage checks are now in CI; its latest result is the verification
authority. Author review has been prepared but not completed. See
[hiring readiness](HIRING_READINESS.md) and [study quality](../evaluation/STUDY_QUALITY_2026-10-12.md).
The historical checkpoint below retains its original scope and open gates.

This checkpoint improves the supported local workflow. It is not a declaration
that all thirteen milestones or the AI teaching acceptance gate have passed.

## Implemented and checked

- Guided Today ? Library ? Study ? quiz/cards ? review journey, direct Study actions,
  readable upload stages, smaller practice batches and automatic first card deck.
- Removed experimental camera/voice and unused telemetry controls from normal study.
  Session controls are shared; quizzes no longer ask for duplicate topic setup.
- Actual HS256 JWTs with compatibility for unexpired legacy tokens. Local recovery
  keys are single-use, hashed in SQLite, rotate after reset and revoke old tokens.
  Legacy password hashes upgrade on successful login to PBKDF2-SHA256/600,000 rounds.
- Persisted session resumption, honest end-session errors, owner-scoped card review
  receipts preventing a lost response from applying another grade.
- Validated source excerpts and source-recall practice when generation fails.
  Internal upload errors stay private; expected input errors remain actionable.
- Existing private data backed up and restored into an isolated directory before
  upgrading. Snapshot locations are recorded in ignored tmp/usability-backup-record.txt.

## What you can do next

1. Try your own readable notes using [the learner guide](../guides/STUDY_GUIDE.md). Write down
   the click and result whenever you cannot tell what to do next. Ask another student
   to try it without explaining the screen; record their difficulties and timing.
2. Review evidence labels in reports/evidence/review-v1.html. Enter your name,
   read the question and passage, choose Enough evidence only if the passage alone
   answers the whole question, otherwise Missing evidence. Explain the supporting
   sentence or missing fact. Choose Unsure when you cannot judge. Start with ten
   decisions, download annotations-author.json and keep it private. Follow
   [the experiment instructions](../evaluation/EVIDENCE_EXPERIMENT.md) to import and train after
   all required splits are reviewed. Author review is not independent ground truth.
   No real labels or measured learned-model gains are currently claimed.
3. If scanned PDFs matter, install Tesseract separately, then install the OCR extra
   with `uv sync --locked --extra ocr` and rerun the OCR checks. Readable text notes
   do not need it. The external Tesseract executable is currently absent.
4. If a Docker demonstration is required, install Docker Desktop with Compose,
   run `docker compose config`, and follow README's Docker instructions. Docker
   is unavailable on this machine, so container build/start was not verified here.
   Check port 8000 availability or change the host mapping before starting.

## Engineering work still required before a full release claim

- Bind owned goals into versioned study context; finish source provenance and quiz
  editing; test closing a session-creation dialog while its request is pending.
- Expand held-out semantic grounding checks. A valid citation is not proof that an
  answer is supported. Existing local models have failed unsupported-question tests.
- Finish reviewed training/calibration, all baseline comparisons and MLflow tracing;
  adopt a model only if the frozen validation/test gates pass.
- Keep camera excluded until backend consent enforcement, bounded image decoding,
  dependency setup and physical-device privacy tests are complete.
- Repeated live acceptance/performance runs, student learning validation, final course
  report and recorded demonstration remain. Do not turn one successful workflow
  into invented accuracy, user adoption or learning improvements on your resume.
- This is a private local app. Public deployment needs a separate session/storage/
  HTTPS security review; browser bearer tokens currently use local storage.

## Real-model result

The three-item journey initially failed on an uncited explanation and invalid quiz.
Both failures remain in live-journey-usability-3-v1.json. The second real journey
completed with a **source-excerpt tutor fallback** and **source-recall quiz fallback**;
its report records those modes explicitly. Cards came from local generation.
This verifies recovery and persistence mechanics, not reliable AI teaching.
Quoted passages may be relevant without fully answering; recall practice emphasizes
wording. The baseline model remains phi3:mini and no model was automatically downloaded.
