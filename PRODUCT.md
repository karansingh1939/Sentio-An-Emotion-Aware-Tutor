# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

College students studying their own course material: lecture slides, PDFs, Word and text notes. They come back across a term to understand a lecture, practise it, review what is fading and prepare for exams. They often work on a laptop without a GPU and with no budget for paid AI services.

Other readers meet Sentio through the student's experience. Design decisions serve the student first.

## Product Purpose

Sentio is a free, local study workspace. It turns a student's own notes into cited explanations, quizzes, flashcards and a revision plan. Success looks like this: a student uploads their notes, gets an explanation they can check against the source, practises, reviews on schedule, restarts the app and has lost nothing.

## Positioning

Sentio answers only from the student's own notes. Every answer cites the slide or page it came from, and it refuses when the notes don't cover the question, without calling the model at all. The model, the database and the files all stay on the student's machine. A general chatbot or a cloud tutor cannot honestly make that claim.

## Operating Context

- Main areas: **Today** (what to continue, due work, goals), **Library** (owned material, courses, previews), **Study** (tutor plus source evidence, slide-by-slide study), **Review** (quizzes, flashcards, mistakes), **Progress** (assessment evidence, topic mastery, syllabus coverage, history) and **Settings** (privacy, diagnostics, camera consent).
- Main loop: upload → cited explanation → practice → review → come back later.
- Long-running work (ingestion, quiz and card generation) runs as background jobs with progress, cancellation and retry. Answers stream, and their sources arrive before the answer text.
- Students study for long sessions and come back daily, so the app has to stay calm and readable over hours of use, in light and dark themes.

## Capabilities and Constraints

- Runs as one local process: FastAPI and Python 3.12, modular browser JavaScript with no build step, SQLite, embedded Qdrant and Ollama (`qwen2.5:7b` recommended). No paid services and no GPU requirement.
- Retrieval is hybrid (BM25 plus embeddings), followed by an evidence gate, schema-checked generation and citation validation. When generation fails, Sentio shows the retrieved passages and labels them as a fallback.
- Practice: quizzes with provenance (model, cited pages, note versions), editable flashcards and FSRS spaced repetition. The next review interval is shown on each rating.
- Topic mastery comes from slide titles and page headings and uses these states: Not started, Practising, Ready, Review due. Mastery fades over time through FSRS.
- Syllabus progress matches syllabus topics to lecture topics, weighted by module hours, and lists gaps the notes don't cover. Users can correct matches.
- The camera and emotion-aware tone are an opt-in, consented, experimental side feature, loaded lazily. They are never central to the product or required for any flow.
- Saved material works without AI. Incomplete turns never count as learning.
- Internal IDs are not normal product content.
- Public deployment and billing are out of scope.

## Brand Commitments

- Name: **Sentio**. One-line promise: "A local AI study tutor that answers only from your own notes."
- Voice is honest and plain. Show uncertainty, fallbacks and missing evidence openly, and never dress them up.

## Evidence on Hand

- Product screenshots in `docs/images/` (Today, Library, Study, Quiz, Flashcards, Progress; light and dark; 1280 and 390 widths) and `docs/images/journey.gif`.
- Measured results in `docs/evaluation/` and `reports/`: a four-model grounding comparison, a retrieval comparison and a grading follow-up. These are synthetic, author-labelled experiments. They do not establish real-world accuracy or learning gains.
- Syllabus-matching labels were written with an AI assistant, not by students. Never present them as student validation.
- There are no testimonials, user counts, institutional adoption or learning-outcome data. Do not fabricate any.

## Product Principles

1. **Evidence before answers.** Every claim points back to the student's notes. When the notes don't cover something, say so plainly.
2. **Honest states over smooth ones.** Fallbacks, refusals, failed jobs and uncertain mastery are shown as what they are.
3. **The student's work is never lost.** Sessions, reviews, schedules and documents survive restarts, upgrades and failures.
4. **Local and free by default.** Nothing requires a GPU, an account with a vendor or a network service.
5. **Study flow first, features second.** Optional extras such as the camera stay out of the way of the main loop.

## Accessibility & Inclusion

Keyboard access with visible focus, accessible controls, safe text rendering, light and dark themes, reduced-motion support, and responsive layouts that work at 390 px, 768 px and desktop widths in both themes.
