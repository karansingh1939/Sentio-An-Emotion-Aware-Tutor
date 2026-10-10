# Sentio project analysis

Reviewed: 2026-09-30. Scope: the current working tree of `Sentio-An-Emotion-Aware-Tutor/Sentio-An-Emotion-Aware-Tutor`, including existing uncommitted changes.

## Assessment and limits

Sentio is a substantial local learning-app prototype with functioning implementations of authentication, document ingestion and retrieval, adaptive tutoring, quiz generation/grading, flashcards, whiteboards, and learner analytics. It needs stabilization before adding features or treating it as production-ready. Several cross-feature contracts are inconsistent even where individual components have tests.

This is a source-based architecture and implementation review with targeted executable checks, not a completed live acceptance test. The project's Python environment cannot start because its base Python 3.12 installation is missing. The available separate Python runtime lacks FastAPI, TensorFlow, pytest, and Graphify. Consequently, full backend tests, live AI quality, model accuracy, webcam operation, browser accessibility, concurrency, and deployment have not been verified here. No dependencies were installed, no model training was started, and no user records were modified.

The saved Graphify report describes 2,013 nodes and 3,508 edges and was used as a navigation aid. Its query launcher failed because of the missing Python installation. Current source, rather than the graph or historical release reports, is the authority for findings below.

## Inventory

- 105 Python files checked for syntax across the package, root scripts, scripts directory, and tests.
- 16 JavaScript source files checked for syntax.
- 51 HTTP/WebSocket route decorators in `sentio/api/app.py`.
- 16 Python test modules containing 93 test functions/methods, plus a Node quiz-view contract check. These counts do not imply passing coverage or count parametrized cases separately.
- Ten tracked files were already modified before review, including authentication, routes, persistence, quizzes, configuration, and tests. Many reports and test/data artifacts were also untracked.
- Largest Python source files: API 1,295 lines; knowledge base 1,003; session coordinator 990; emotion detector 732; tutor agent 655; structured parser 639.
- `models/emotion_model.h5` exists, is 58,048,408 bytes, and has an HDF5 file signature. Loading and prediction quality remain unverified.
- `data/fer2013.csv` is 234 bytes: Git LFS pointer text plus an appended PowerShell launch command. It is not the dataset. The pointer names a 301,072,766-byte object.

## Product and architecture

The PRD describes a college-student learning copilot. The current scope is much larger than the original webcam emotion tutor in the README.

| Area | Implementation | Current role |
|---|---|---|
| Browser | `static/index.html`, `static/js/app.js`, core store/router/API, view controllers, `core/legacy.js` | Vanilla JavaScript single-page application with hash routes; legacy globals still drive chat and camera |
| API | `sentio/api/app.py` | FastAPI routes, authentication/ownership checks, upload handling, privacy endpoints, WebSocket emotion processing |
| Authentication | `sentio/auth/` | Password hashing, signed access/refresh tokens, account lookup, role checks, audit/consent storage |
| Tutoring | `sentio/tutor/tutor_agent.py`, `orchestrator.py` | Coordinates emotion, session state, learner memory, retrieval, prompts, model output |
| LLM | `sentio/ai/providers.py`, `coordinator.py`, `prompts.py`, parsers/history | Ollama by default; optional OpenAI/HuggingFace providers; JSON output and bounded in-memory conversation context |
| Retrieval | `sentio/rag/`, `sentio/ingestion/`, document repository | PDF/DOCX/TXT extraction, overlapping character chunks, MiniLM embeddings, Qdrant and BM25 fusion, citations |
| Emotion | `sentio/ai/emotion_detector.py`, training script | OpenCV face detection, 48×48 grayscale CNN inference, smoothing, expression-to-learning-state mapping |
| Attention | MediaPipe logic in `static/js/core/legacy.js` | Browser landmarks, eye/head heuristics, aggregated telemetry sent to backend |
| Learning records | `sentio/session/`, `sentio/persistence/db_client.py` | In-memory active sessions; SQLAlchemy/SQLite tables for sessions, quizzes, mastery, documents, decks, boards, identity |
| Learning analytics | `sentio/intelligence/` | Deterministic mastery/confidence/forgetting/misconception/recommendation/path/adaptation calculations |
| Practice tools | `sentio/quiz/`, `flashcards/`, `whiteboard/` | Structured quiz generation and scoring, SM-2-style scheduling, drawing persistence and Pillow export |

The supported application entry point is `uvicorn sentio.api.app:app`. Startup validates production configuration and loads a process-wide TutorAgent. The configured defaults are Ollama `phi3:mini`, MiniLM embeddings, persistent local Qdrant, and a SQLite file under `data/`.

### Main flows

**Tutor chat:** browser message and optional JPEG → authenticated session ownership check → emotion detection and session update → LangGraph memory lookup → keyword-selected research/quiz/planner/feedback/tutor route → model completion → parsed response → in-memory conversation and session metrics → browser rendering.

**Uploaded material:** authenticated upload → student/category directory → extraction → 500-character chunks with 100-character overlap → SQLite chunks → embeddings → Qdrant → indexed status. Retrieval combines vector and BM25 candidates and returns selected source snippets/citations.

**Quiz:** active session and document scope → retrieval → structured generation → saved quiz → server-side answer comparison or short-answer grading → per-question attempt/mastery updates → model-written summary. The recent working-tree changes enforce student/document scope and use the chosen topic for mastery records.

**Flashcards:** deck → topic-based generation → saved cards → due queue → review quality → next-review scheduling and mastery update. Its retrieval contract differs from quizzes and does not pass document scope.

**Emotion and attention are separate:** chat can send frames to the backend CNN; the browser also computes attention locally and posts aggregate measurements. A server emotion WebSocket exists, but no `new WebSocket` client construction was found in the current frontend. Continuous browser attention tracking therefore should not be described as continuous server CNN inference.

## Prioritized findings

### High priority: correctness, privacy, and reliability

1. **Tutor output is inserted as unsafe HTML.** `static/js/core/legacy.js:459` transforms Markdown without escaping ordinary text, and `appendTutorMessage` inserts the result through `innerHTML`. A Node check confirmed that an image element containing an event handler survives unchanged. Tokens are stored in localStorage, increasing the consequences of script execution in this page. Render model output through a safe text/Markdown boundary; inspect other dynamic HTML insertion sites at the same time. Browser exploitation was not attempted.

2. **“Delete all data” leaves substantial data behind.** `sentio/auth/repositories.py:73` deletes a subset of tables through individually committed statements. It does not remove documents/chunks, Qdrant vectors, uploaded files, quizzes/questions, deck records, whiteboards, saved emotion JSON logs, or live session/history caches. `sentio/api/app.py:811` calls only this repository method. Implement one explicit lifecycle spanning those stores, with recoverable failure handling. This is an implementation finding, not a legal compliance assessment.

3. **Camera control and consent have competing states.** `legacy.js:6` declares `let camStream`, whereas `app.js:77` and `:92` check `window.camStream`. A JavaScript check confirmed that the former does not populate the latter. The route-based stop condition therefore does not see the active stream. Settings changes `telemetryActive`, while the camera consent modal uses a separate localStorage-backed flag; settings does not directly stop capture or persist server consent. Unify the camera lifecycle and verify settings, navigation, logout, and revocation with a real browser.

4. **Selected-document chat can skip retrieval.** `sentio/tutor/orchestrator.py:299` routes using message keywords, independently of document selection. Executing the current routing method sends “Summarize my uploaded notes” and “Give an example from this document” directly to the tutor; “Explain this chapter” goes through research. Direct tutor calls receive no retrieved content. A document-grounded session needs an explicit retrieval contract and a clear no-evidence response.

5. **Flashcards are not grounded in the selected documents.** `sentio/flashcards/flashcard_service.py:30` does not pass `student_id` or `document_id` to retrieval and obtains its subject from the first process-wide session. The knowledge base requires student and document scope for private-document retrieval. Pass the requesting learner's intended context explicitly; avoid choosing another session's subject. This does not by itself prove a private-document disclosure.

6. **Emotion smoothing is shared across sessions.** One TutorAgent owns one detector, including its smoother and last result (`sentio/ai/emotion_detector.py:376`). Both chat and WebSocket requests use that detector. Interleaved learners can influence one another's smoothed predictions. Keep model weights shared but prediction history per session; verify concurrent requests once the runtime works.

7. **Missing model weights enable an untrained predictor.** `sentio/ai/emotion_detector.py:405` builds a new random-weight model when the saved file is absent. That can present meaningless output as emotion inference. Model absence should disable inference explicitly. Separately, the training CSV must be restored before training is possible; the saved model means retraining is not automatically required to run the app.

8. **Quiz submission can record progress before failing.** `sentio/quiz/quiz_service.py:147` writes attempts/mastery per question and only afterward requests an LLM summary. A summary outage can return a failure after those changes are committed. Retrying can count the same submission again; no submission idempotency guard is evident. Separate deterministic scoring/persistence from optional summary generation and make a submission durable once.

9. **Model schemas permit values downstream code cannot handle.** `QuizQuestion.correct_answer` allows null, but scoring calls `.strip()` unconditionally (`quiz_service.py:170`). Question type/difficulty are unconstrained strings and empty question lists are accepted. Enforce semantic invariants at the structured-output boundary, including valid answers and options, rather than relying only on prompting.

10. **Document fallback is incomplete.** Ingestion saves chunks but requires embedding creation and successful Qdrant indexing to mark a document indexed. Retrieval considers only indexed documents. Thus the BM25 fallback can help with previously indexed documents, but it does not make new uploads usable when vector indexing fails. Represent text-search readiness separately from vector readiness or make the user-visible failure explicit.

11. **Chat masks the intended service-unavailable response.** The app registers a 503 handler for `LLMServiceUnavailableError`, but `sentio/api/app.py:430` catches all chat exceptions and converts them to HTTP 500. Preserve the typed failure. Legacy chat also bypasses the shared client refresh flow and checks `data.text` rather than HTTP success, so expired authentication and provider failures become generic “no response” messages.

12. **Request cost is insufficiently bounded.** Uploads copy files without an application byte limit; webcam frames have no route-level size/dimension bound; whiteboard export accepts arbitrary canvas dimensions and shape counts; quiz/card counts lack useful bounds. Rate limiting does not cap the cost of one accepted request. Add limits at the existing request boundaries before serving untrusted clients.

### Medium priority: persistence and integration

- Conversation history is held in a deque and is not persisted. Session rehydration restores only part of the session state; quiz/emotion trackers and difficulty history are not reconstructed. Current exchange recording updates memory without saving the session immediately. Clarify what “resume” guarantees across reload, graceful restart, and crash, then test those guarantees.
- `HistoryView` is a placeholder despite history APIs being present. Planner and feedback graph nodes are stubs, although a separate deterministic learning-path engine exists. The whiteboard saves and exports drawings but is not a vision-based tutor that interprets a student's canvas.
- Recorded quiz attempts use the literal `student_answer="answered"` and a binary score. Rich short-answer/partial-credit results returned to the browser are lost in the learning record, limiting later misconception analysis.
- Quiz generation returns correct answers with the questions. That may be acceptable for self-study, but the current contract cannot support hidden-answer assessment without a separate public representation.
- Document identity includes category, while existing-document lookup uses filename and student only. Same-name documents across categories can be treated inconsistently. Re-indexing also deletes prior records/vectors before replacement succeeds.
- Admin document sync scans the legacy category-first tree, while uploads use student-first directories. It is not a complete rebuild/recovery path for current uploads.
- Qdrant connection failures can fall back from server to local disk and then memory. Persisted “indexed” document records do not prove that the active vector store contains those vectors. Surface the effective mode and recovery state.
- Upload parsing, embedding generation, and indexing run synchronously inside an async route. WebSocket inference also runs directly in its async loop. These paths can delay unrelated work; move blocking operations off the event loop and measure before introducing a queue.
- Session caches, diagnostic traces, and per-IP limiter entries lack a clear eviction lifecycle. Local single-process use is the realistic current deployment model; multi-worker operation would also split session/history state and contend for local Qdrant storage.
- Logout clears identity tokens but does not call the store's existing `clearAuth()` or visibly reset all legacy session/camera state. Backend ownership checks are valuable protection, but browser account-switch state still needs an end-to-end check.
- Privacy export selects a subset of stored learning data and omits several artifact types. Telemetry deletion removes SQL rows but does not purge all cached/serialized emotion representations. Export/delete should share a defined inventory of owned data.

## ML and learning quality

The training code supports CSV and image-folder loading, augmentation, class weights, callbacks, held-out evaluation, and optional transfer backbones. Runtime classes map seven expressions to teaching states by fixed rules. Those mappings and the learner-engine thresholds are design assumptions, not demonstrated measures of understanding.

The folder loader expects names from `EmotionConfig.CLASSES`, including `disgusted`, `fearful`, and `surprised`; a dataset arranged using different folder names will silently skip those directories after warnings. Validate labels and counts before training. Confirm which training run produced the supplied HDF5 model, its class order, input preprocessing, and held-out metrics before quoting accuracy.

Analytics are primarily deterministic formulas over persisted learning evidence, not an independently trained learner model. The live intelligence service starts from persisted mastery and applies prerequisite propagation, confidence decay, forgetting estimates, and recommendations. Their usefulness needs real learner evaluation. `docs/HUMAN_BETA_RESULTS.md` explicitly leaves genuine human testing pending; historical engineering reports are not evidence of learning outcomes.

## Setup, deployment, and documentation

- Both the project virtual environment metadata and the tested `C:/Sentio/.venv` launcher reference the missing Python installation. `python` is also absent from the current shell PATH. Repair/recreate a project environment before making runtime claims.
- `requirements.txt` uses lower bounds rather than a reproducible lock and installs several heavy backends together. Test tools such as pytest/Playwright are not declared there, despite tests importing them.
- CI and `scripts/run_tests.py` use unittest discovery. Pytest-style test functions and fixtures, notably grounded-study-loop tests, are not executed by unittest discovery; missing pytest can also cause import errors. `tests/run_isolated_tests.py` uses pytest but hardcodes a list that omits newer grounded-study-loop and learning-identity modules. Consolidate the test entry point and isolate temporary databases.
- Several older tests mutate shared configuration and fixed database paths. Their order and process isolation matter. A historical pass count is not a fresh pass of the current working tree.
- Docker Compose includes a static signing secret, does not enable production mode, and sets `DB_URL` while application configuration reads `DATABASE_URL`. Ollama's configured `localhost` refers to the container itself, and no Ollama service is defined. The container deployment path needs a real smoke test and explicit service configuration.
- No `.dockerignore` was found at the project root. `COPY . /app/` can include local data, environments, and artifacts from this populated working tree.
- README paths and descriptions drift from implementation: old configuration/package names, default model descriptions, Qdrant mode, and claims about readiness differ across documents. The README's optional-backend launch command also uses `app:app` rather than the package entry point.
- MediaPipe is fetched from a CDN and its model from a remote host. A fresh browser cannot be assumed to have the camera feature available offline even though Ollama can run locally.
- `.gitignore` misses several active artifacts, including `.venv`, SQLite WAL/SHM files and the actual local Qdrant directory. Preserve the existing work, then establish a clean reproducible baseline.

## Verification performed

| Check | Result | Limit |
|---|---|---|
| Python AST parsing | 105 files passed | Does not verify imports or runtime behavior |
| JavaScript parsing with Node VM | 16 files passed | Does not verify DOM or browser behavior |
| `node --experimental-vm-modules tests/test_quiz_view.mjs` | Passed | Mocked UI/API contract, not live browser/backend |
| Existing `sentio/rag/bm25.py` smoke check | Passed | Small keyword-search examples only |
| Current router method executed in isolation | Confirmed document-oriented messages bypass research | Does not measure generated answer accuracy |
| Current Markdown renderer executed in Node | Unsafe HTML preserved unchanged | No browser attack performed |
| JavaScript lexical-global check | `let camStream` is not `window.camStream` | Full camera lifecycle still needs browser validation |
| Training asset inspection | CSV is pointer/command text; HDF5 signature present | No training, model load, or inference evaluation |
| Full backend/browser/AI suites | Not run | Broken Python environment and missing dependencies |

## Suggested work sequence

1. Preserve current changes and recover a working project Python environment. Restore the CSV only if training is part of the next task. Establish one isolated test command and record an actual baseline.
2. Fix unsafe rendering, camera/consent lifecycle, complete deletion, request bounds, and shared per-user emotion state.
3. Finish one complete study loop: own document → grounded chat → grounded quiz → retry-safe grading → durable mastery. Reuse the existing components and recent ownership fixes.
4. Apply the same explicit context contract to flashcards. Define session/history durability and connect the history UI.
5. Reconcile documentation with measured behavior; test cold startup, provider failure, restart, account switching, camera denial, and a real learner session.

A framework rewrite, new agent layer, or more features is not needed to address these findings. The existing modules can support the next stage once their boundaries and lifecycle behavior are made consistent.
