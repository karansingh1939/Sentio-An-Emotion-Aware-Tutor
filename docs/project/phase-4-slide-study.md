# Phase 4: study with slides, camera optional

Shared contract for the Phase 4 team. Each engineer builds only the files they own, against
the interfaces below. The stubs in the listed modules fix every name and signature; change
one only through the product manager.

## What the student gets

From Library, **Study slides** beside a lecture opens `#/slides`: the lecture slide by slide
(title and text), Previous / Next, and **Explain this slide**. The tutor explains the
current slide from that slide first and answers follow-up questions about it, with
citations. A **Camera** switch is shown only when the emotion feature is enabled; it needs
the learner's consent, as today. With the camera on, a small mood chip shows the camera's
guess (labelled as a guess) and, after sustained confusion, offers "Want a simpler
explanation?"; after sustained distraction, "Take a short break?". Mood changes only the
tone of explanations, never difficulty, sources or the evidence check.

## Interfaces

### Slides (backend owns `repositories/slides.py`, `api/routes/slides.py`)

- `SlideRepository(engine).slides(owner, document_id)` returns
  `{"document_id", "filename", "slides": [{"number", "title", "text", "topic_id", "topic_title"}]}`
  for an indexed document the owner has, else `None`. One entry per page or slide that has
  text, in order. `title` is the slide's topic heading if the slide starts a topic, else the
  first line; `topic_id` and `topic_title` come from the lecture's topic map
  (`TopicRepository.document_topics`).
- `SlideRepository(engine).slide(owner, document_id, number)` returns one slide dict plus
  `"filename"` and `"document_id"`, or `None`.
- `GET /api/v1/documents/{document_id}/slides` returns `slides()`, or 404.
- `PUT /api/v1/sessions/{session_id}/slide` with body `{"number": int}` stores
  `session.metadata["slide"] = number` and returns `{"number": number}`. It returns 404 when the
  slide does not exist, and 409 unless the session's `document_id` is a single document id
  (not "all", a course or a list).
- Sessions for slide study are created as usual with metadata
  `{"document_id": <id>, "mode": "slides"}`. `mode` is optional; "slides" is its only other
  value. Changing notes (`/grounding`) clears `slide` and `mode`.

### Mood (ML owns `emotion/policy.py`; backend exposes it)

- `study_mood(events, now)` takes `EmotionEvent`s (`timestamp`, `emotion`, `learning_state`,
  `confidence`; oldest first) and returns
  `{"learning_state", "confidence", "since", "nudge", "fresh"}`:
  - `learning_state` is a key of `tutor_cfg.STRATEGY_MAP`;
  - `confidence` is from 0 to 1;
  - `since` is the time the state began, or None;
  - `nudge` is `None`, `"simpler"` or `"break"`;
  - `fresh` is false when there is no confident reading in the last `MOOD_WINDOW_SEC`, in
    which case the state is "neutral".
- `GET /api/v1/sessions/{session_id}/mood` returns `study_mood(session's emotion timeline)`
  plus `"label"`, a plain word for the chip: "focused", "unsure", "distracted" or "calm".
  It is guarded like the other camera routes: 404 when the feature is off, and the
  learner's consent is required (`require_emotion_access`).

### Tutor (ML owns `tutor/slides.py` and the slide branch in `tutor/orchestrator.py`)

- `slide_content(kb, subject, topic, difficulty, slide, nearby)` returns the
  `RetrievedContent` for explaining a slide: that slide as Citation Index 1, then up to 3
  `nearby` passages (retrieved from the same lecture for the question). `SLIDE_INSTRUCTION`
  is the prompt rule for explaining one slide to a student.
- In a session with `metadata["mode"] == "slides"` and a `slide`, the retrieve step uses
  `slide_content` instead of plain retrieval. The evidence gate, citations and streaming
  are unchanged.
- The tone uses `study_mood(...)["learning_state"]` when it is `fresh`, and otherwise the
  current learning state. It is tone only.

### Page (frontend owns `static/js/views/slides.js` and its markup, styles and route)

Element ids the QA tests use:

- `#slides-view`, `.slide-item` (list entries), `#slide-title`, `#slide-text`;
- `#slide-prev`, `#slide-next`, `#slide-explain`, `#slide-question` (input), `#slide-ask`;
- `#slide-answer` (where the explanation streams);
- `#slide-camera-toggle`, `#slide-mood`, `#slide-nudge`, `#slide-nudge-accept`;
- `[data-action="study-slides"]` on the Library lecture row.

Accepting the "simpler" nudge asks "Explain this slide more simply." Accepting "break"
pauses for 2 minutes with a countdown.

## Rules for every engineer

- Work only in your own files; ask the product manager before touching others.
- Never use the real webcam, the user's `data/` folder, or the process on port 8000.
- Download nothing. Tests use fake models, fake detectors and fake camera input.
- Match the surrounding style. Every behaviour gets a test.
- Run Ruff, Prettier for JavaScript, and your tests before reporting.
