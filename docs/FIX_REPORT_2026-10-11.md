# Sentio repair and improvement report

Completed 11 October 2026. Scope: the local tutor application, authenticated
study workflows, data persistence, browser rendering, and build/test setup.
Existing repository migration and unrelated user changes were preserved. No
commits, deployment, or remote publishing were performed.

## Repairs

- **Persistence:** repeated initialization no longer discards in-memory SQLite
  state. Worker threads share the same in-memory database. Restored sessions
  reload their recorded quiz attempts.
- **Quiz reliability:** generation rejects empty or unusable questions and
  invalid answer keys. Objective scoring works when summary generation fails.
  Identical submissions replay saved results without counting progress twice.
  Attempts, mastery, results, and session snapshots commit together; failed
  writes restore runtime state and can be retried. Semantic grading validates
  score ranges and correctness, and returns a retryable error when unavailable.
- **Document ingestion:** category and owner distinguish identically named
  files. Empty or failed replacements preserve existing content. Uploads are
  staged, limited to 20 MiB, and restricted to supported text document types.
  Successful text extraction remains usable by keyword search when embeddings
  fail. Retrieval avoids retrying an embedding model for keyword-only documents.
  Disk sync scans learner folders and prunes exact document identities.
- **Grounding:** flashcards use the learner's session and selected document.
  Cross-owner sessions and documents are rejected. The source selector remains
  visible during active tutoring, so learners can switch sources without ending
  their session.
- **Emotion isolation:** smoothing and throttling state are separate for each
  session. No-face frames clear prior detections. Session closure clears the
  detector's cached state. WebSocket inference runs outside the event loop.
- **Privacy:** account deletion removes owned study artifacts, files, cached
  sessions, and emotion log files. Export includes document and study artifact
  inventories without password hashes or refresh credentials. Telemetry deletion
  clears stored events, cached timelines, diagnostic traces, and emotion files.
- **Browser behavior:** untrusted model and document text is escaped before
  HTML rendering. Corrupt saved user JSON no longer breaks startup. Logout
  clears session state and stops camera/speech activity. Camera models initialize
  when camera capture starts. Routing waits for authentication, and normal
  learner accounts do not see the admin disk-sync action.
- **History and Analytics:** the placeholder screens now show recent sessions
  and actual mastery/profile data, with loading, empty, and retry states.
- **Build and verification:** CI and Docker use `uv.lock` and the `src` package
  layout. Compose uses its own Ollama service and requires a supplied secret.
  The normal runner uses pytest; the isolated runner discovers current test
  modules. Ruff and Prettier checks are clean. Runtime data and local analysis
  output are ignored by Git.

## Validation evidence

- Complete Python suite: **131 passed, 31 subtests passed**, including real
  Chromium workflows against an HTTP API server.
- Four JavaScript regression scripts passed: quiz controls, tutor rendering,
  escaped study-tool/history/analytics rendering, and saved-state/logout behavior.
- `ruff check`, `ruff format --check`, `npm run format:check`, and
  `git diff --check` passed.
- `uv lock --check` passed, and source distribution plus wheel builds succeeded.
  The wheel includes the web assets.
- Local environment verification passed: required packages, SQLite, persistent
  Qdrant, and emotion weights are available.
- A separate application lifecycle used the **real Ollama `phi3:mini` provider**
  and the real emotion model weights, registered/logged in a temporary account,
  created a session, and returned an HTTP 200 chat response. The observed chat
  latency was approximately **29.6 seconds**. This smoke test used a temporary
  home and did not change learner data.
- The normal launcher was checked on **http://127.0.0.1:8001**.

Automated tests use deterministic AI fixtures and temporary databases to verify
application behavior. They do not establish the factual quality of generated
teaching material or emotion recognition accuracy. The live chat smoke check
provides separate evidence that the installed provider works.

## Improvements, in priority order

1. **Measure learning quality.** Add a small reviewed question/document set and
   score factual correctness, citation support, question difficulty, and grading
   consistency. Validate emotion recognition with a labelled dataset and actual
   webcam sessions; do not treat its inferred learning state as ground truth.
2. **Reduce model wait times.** Measure warm versus cold responses, preload the
   chosen model, add streaming responses and explicit generation progress, and
   move ingestion/generation to bounded background jobs. The observed 30-second
   response is the clearest user-facing performance limit.
3. **Finish document support.** Add OCR for scanned PDFs and images, cancellation
   for long uploads, and extraction/indexing progress. Add relevance evaluations
   for keyword-only versus semantic retrieval before changing ranking weights.
4. **Make deployment verifiable.** Run the Docker build and Compose smoke flow,
   then pin the Ollama image to the tested version/digest. Exercise backup and
   restoration, TLS, proxy request-size limits, and shared rate limits before
   enabling multiple workers or exposing the service publicly.
5. **Simplify maintenance.** Split the large tutor runtime, session manager,
   emotion detector, and retrieval modules by responsibility. Separate optional
   training/heavy model dependencies where practical. Replace duplicated UI
   session controls gradually, keeping the working flows covered by browser tests.
6. **Expand the study dashboard.** Add history pagination beyond the current
   latest 50 sessions, session detail summaries, mastery trends, and goal tracking.

## Practical limits

Docker is not installed on this machine, so container execution was not verified.
The hosted CI workflow was updated but has not run remotely. A physical webcam
was unavailable; camera capture and recognition accuracy remain unverified.
OpenAI and Hugging Face providers were not exercised. Scanned PDFs and image
uploads still require the OCR improvement described above.

This is a verified repair of the covered local workflows, not a claim that every
possible deployment, provider, concurrency level, or model output is bug-free.

Build configuration follows the official
[uv Docker guide](https://docs.astral.sh/uv/guides/integration/docker/) and
[uv GitHub Actions guide](https://docs.astral.sh/uv/guides/integration/github/).
SQLite pooling follows the
[SQLAlchemy SQLite documentation](https://docs.sqlalchemy.org/en/20/dialects/sqlite.html).
