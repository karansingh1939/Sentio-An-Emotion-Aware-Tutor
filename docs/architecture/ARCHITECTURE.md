# Sentio local architecture

This records the implemented boundaries and remaining gaps. It is not a claim that
every release milestone has passed.

**Style:** a local-first modular monolith. One FastAPI process serves the API and a
framework-free browser UI; requests flow `routes → services → repositories → SQLite`,
with SQL only in repositories. Generation runs on a local Ollama model.

```mermaid
flowchart TD
    UI[Today · Library · Study · Review · Progress] --> API[Owner-scoped FastAPI]
    API --> Stream[Stream service and request receipts]
    API --> Jobs[Durable bounded jobs]
    Stream --> Tutor[Study orchestrator]
    Jobs --> Library[Staged ingestion and recovery journal]
    Jobs --> Practice[Quiz and flashcard services]
    Tutor --> Retrieval[Owned active chunks · keyword and dense ranking]
    Retrieval --> Gate[Relevance heuristic and citation references]
    Gate --> Ollama[Installed local Ollama model]
    Practice --> Ollama
    API --> Planning[Deterministic planning and review scheduling]
    Library --> Files[Owner-scoped document files]
    Library --> Qdrant[Qdrant derived index]
    Retrieval --> Qdrant
    Stream --> SQL[SQLite and versioned migrations]
    Jobs --> SQL
    Practice --> SQL
    Planning --> SQL
    Library --> SQL
    Offline[Reviewed offline experiments] --> Artifacts[Reports · trusted local model artifact]
    Offline -. optional .-> MLflow[Local MLflow]
```

One running API owns persistent storage through a process lease. SQLite is
authoritative for active document revisions, saved practice, review receipts,
study plans and request state. Qdrant contains a derived index; retrieval checks
active registered chunks instead of accepting abandoned staged vectors.
Backup requires the application to stop and verifies checksums on restore.

The AI and ingestion lanes each have one worker; pending work is bounded.
Cancelled or interrupted generation is not replayed automatically. Durable
request receipts distinguish retrying an unknown submission from creating a new
job. Practice captures an owned session/source snapshot, publishes against that
snapshot inside a final SQLite transaction, and returns it with job status.
The browser checks current context again before displaying finished work.

```mermaid
sequenceDiagram
    participant B as Browser
    participant A as API
    participant J as Durable job
    participant R as Retrieval
    participant O as Ollama
    participant S as SQLite
    B->>A: Submit practice with stable request ID
    A->>S: Check owner, receipt and source snapshot
    A->>J: Queue frozen context
    A-->>B: Job ID
    J->>R: Retrieve owned active passages
    R-->>J: Selected evidence
    J->>O: Generate with exact-count schema
    O-->>J: Structured output
    J->>J: Validate output and cancellation
    J->>S: Transaction: recheck owner/session/source versions and save
    S-->>J: Commit or reject stale work
    B->>A: Poll job and current study context
    A-->>B: Status, result and snapshot
    B->>B: Display only if context still matches
```

Streaming emits status, readable text deltas and a final validated result.
Stop closes the provider response. A completed request is saved once with its
context; replay returns the saved result without incrementing exchanges again.
Replacing a same-named document changes its checksum and invalidates old context
and history. Citation checks establish reference membership, not semantic truth.

## Tutor workflow (LangGraph)

```mermaid
flowchart LR
    memory_lookup --> retrieve
    retrieve -->|insufficient selected evidence| refuse
    retrieve -->|evidence or general study| generate
    refuse --> END
    generate --> END
```

`memory_lookup` adds learner history, mistakes and the session goal. `retrieve` runs
hybrid keyword/dense search over the owner's active chunks and classifies evidence.
`refuse` answers without the model when selected notes do not support the question.
`generate` asks Ollama for schema-constrained JSON, validates citations against the
retrieved passages, and falls back to labelled source excerpts. Quizzes, flashcards and
plans have their own endpoints and jobs rather than graph branches.

A session studies from `all` notes, one document, a list, or `course:<id>`. Courses
(`repositories/courses.py`) are optional folders; `expand_source` resolves a course to its
current documents at question time, so retrieval, the stale-context fingerprint and
practice snapshots include lectures added after the session started. Sessions saved
without notes (`none`) get a fixed "choose notes" reply from the `refuse` node; there is no
built-in curriculum or ungrounded tutor. PowerPoint decks are parsed with `python-pptx`,
one page per slide (title, text, tables, speaker notes).

When the stream is open, `retrieve` emits a `sources` event, so the browser shows the
passages before the answer arrives.

Schema-constrained generation goes through one helper, `generate_structured`, used by
quizzes, flashcards and document overviews: a mismatch (`InvalidModelOutput`) is
repaired or regenerated before any fallback. A document overview (summary, key
concepts, suggested questions) is written as a background job from the document's
opening passages and cached on the document row against its checksum.

Difficulty (`tutor/difficulty.py`) has one policy: the learner's chosen level moves one
step only on an explicit chat request (phrase patterns, not single words) or a quiz
streak (3 correct up, 2 wrong down; the streak restarts after a change). `POST
/sessions/{id}/difficulty` sets and pins a level, which quiz streaks then respect until the
learner asks for a change. Changes are returned as `difficulty_change` (from, to, reason)
on the stream `complete` event and on quiz results. Emotion and the learner model only
shape tone and depth.

Syllabus progress (`study/syllabus.py`, `repositories/syllabus.py`): a pasted or uploaded
syllabus is parsed deterministically into units and topics and stored in `syllabus_items`.
Matching to lecture topics is computed live by word overlap (title words count double over
slide text; plurals normalised), so new lectures match automatically; only the learner's
corrections are stored (`link_mode` auto/manual/none). A syllabus topic's status comes from
the states of the lecture topics it matches, and the course percentage is the share Ready
now: topics due for review are shown separately, so the number falls between reviews. When
every unit states its hours, an item weighs its unit's hours divided by the unit's items.
Words split by PDF extraction are rejoined when the whole word is in the syllabus or the
course's slides and the pieces are not both real words.

Matching stays lexical on measured evidence. `scripts/eval/syllabus_matching.py` compares it
with three uses of MiniLM similarity by nested cross-validation, on one real 72-item syllabus
(24 items in the notes). Labels were written by the AI assistant from the slides, with a
strict "teaches or defines it" rule, so treat the numbers as an engineering check rather than
a student study. Word overlap scored F1 0.56 on links and 0.86 on "is it in the notes" (with
precision 1.00); adding similar topics gave 0.53 and 0.80, filling gaps gave 0.54 and 0.79,
and pruning weak links gave 0.54 and 0.86. Embeddings measure relatedness, and a syllabus
gap is usually close to a slide without being taught by it.

Topic mastery (`study/topics.py`, `repositories/topics.py`): a lecture's topics are page
ranges grouped by heading (slide titles; PDF page headings, skipping running headers),
stored in `note_topics` with the document checksum and rebuilt when it changes. Topic ids
are derived from the owner, document, checksum and first page, so concurrent rebuilds agree.
A generated question names the passage it came from by Citation Index. The server keeps
that when the passage exists and shares at least half as many words with the question as
the best match does; otherwise the best match is used (`quiz_questions.source_document_id`,
`source_page`). Each submitted answer records its `question_id`. A topic's state comes from
the answers whose question page falls in its range, so renaming or merging topics regroups
past answers without re-grading.

Topic practice: a session may carry up to 5 `topic_ids`, checked at creation to be the
student's own and inside the session's notes, and frozen in the study snapshot. Quizzes on
such a session skip retrieval: `KnowledgeBase.topic_content` reads the topics' pages from
`document_chunks`, within 3,000 characters shared between topics, sampling evenly across
long topics. Questions are assigned to topics in turn. A question that fails the passage
check falls back to word overlap within its assigned topic and, failing that, to that
topic's first slide, so a topic quiz always counts toward the topics chosen. A topic that
was merged away or whose lecture changed gives 409. Provenance records the topics and how
each question was placed (`located`: model, overlap or topic).

Topic memory: a topic is scheduled like a flashcard, with no stored schedule. Its quiz
answers (right is Good, wrong is Again) and the ratings in `card_reviews` for cards on its
pages (`flashcards.source_document_id`, `source_page`, set when cards are generated, the
same way as quiz questions) are replayed through `fsrs.review` in time order. Reviews
within a day of a sitting's first one count once, rated by the worst of them. A topic whose
last 3 answers were right is Ready until recall reaches 90%, then `review_due`. Replay keeps
renames and merges working: the state is always derived from page ranges and reviews.

Flashcards are scheduled by `flashcards/fsrs.py`, a dependency-free FSRS-5 model: each
card stores stability, difficulty and its last review time, and the next review is set
for 90% predicted recall. Cards scheduled earlier by SM-2 are converted on their next
review. The learner model reuses the same recall probability for forgetting risk.

## Optional emotion feature

`sentio/emotion` holds the earlier emotion-aware prototype: a FER2013 CNN on the server
and MediaPipe attention estimates in the browser (`static/js/core/emotion_camera.js`).
It is off unless `ENABLE_EMOTION=true`; the server checks the learner's latest saved
consent before accepting telemetry, live frames or chat frames, and bounds frame size
and dimensions before decoding. The detected learning state only adjusts tone and
pacing. See [the emotion guide](../guides/EMOTION.md).

## Other boundaries

Storage and saved browsing are independent of local generation and the emotion
feature. MLflow and training dependencies stay outside normal application startup.
The learned evidence model is not integrated: reviewed labels, baseline parity,
quality/coverage comparisons, latency and live acceptance are still required.

A session may bind one of its owner's active goals. The goal's ID and text are part
of the study context version, so editing, completing or switching it invalidates
in-flight turns and practice. Saved quizzes and cards store provenance (generation
mode, model, cited pages and note checksums). Owners can edit quiz questions; each
edit bumps a quiz revision so earlier submissions replay unchanged while new answers
are graded against the correction.

Remaining architectural work includes broader grounding evaluation and further splitting of legacy modules as their
behavior is migrated. There is no public deployment or external model service
required by this local release.

## Usability checkpoint, 2026-10-12

The supported flow is now Library ? Study ? practice ? review, with guided Today
actions and no normal camera/voice controls. Authentication issues standard HS256
JWTs; migration 8 adds hashed single-use recovery keys and token revocation versions.
Legacy password hashes upgrade on successful login. See STUDY_GUIDE.md and
RELEASE_HANDOFF.md for recovery, supported workflow and open release gates.

A real three-item journey failed validation before fallback integration
(reports/generation/live-journey-usability-3-v1.json). The next journey completed
with source-excerpt tutoring and source-recall quizzes
(reports/generation/live-journey-usability-3-fallback-v2.json). This is a recovery
and persistence result, not an AI teaching or learning-quality improvement.
Earlier unsupported-answer failures remain applicable; citation membership alone
does not establish semantic support. No reviewed evidence-model result is claimed.
