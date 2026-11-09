# Feature audit — 2026-11-06

Branch `feature/premium-frontend` at `b3cc9579`, plus the uncommitted dark redesign that was in
the working tree. Real inputs: `tmp/real-samples/week1.pptx`, `week2.pptx`, `week3.pptx` and
`syllabus.pdf`. Model: `phi3:mini` through local Ollama (the preview home has no `.env`, so the
default model was used, not `qwen2.5:7b`).

## Automated tests

| Suite | Result |
| --- | --- |
| Python unit + integration (`pytest --ignore=tests/browser`) | 433 passed, 1 skipped |
| Browser (Playwright, `tests/browser`) | 17 passed |
| JavaScript (`npm test`) | all 6 files pass |

## End-to-end journey over real HTTP (67 steps)

66 passed. The one failure, `GET /sessions/{id}/mood`, is expected. It needs the optional camera
feature (`ENABLE_EMOTION=true`), which is off on this install.

| Area | Features exercised | Result |
| --- | --- | --- |
| System | health, readiness checks | OK |
| Account | register (recovery key), login, refresh, wrong password rejected, new recovery key, logout | OK |
| Courses | create, rename, list, move a lecture out | OK |
| Library | upload PPTX directly, PPTX and PDF as background jobs, list, preview, slides (36), delete | OK |
| Topics | per lecture (30), course progress, due topics, rename | OK |
| Syllabus | upload PDF (72 items), progress, correct a match, delete | OK |
| Study | session, ground to a lecture, difficulty, context, goals, note overview job | OK |
| Tutor | streamed answer with sources, refusal on an uncovered question, turn history, non-streamed chat | OK |
| Slides | set current slide | OK; mood needs the camera feature |
| Quiz | generate job, open, instant check, edit, submit, saved list | OK |
| Flashcards | deck, generate job, due list, edit, FSRS review, review receipt | OK |
| Planning | preferences, daily plan, feedback | OK |
| Progress | session analytics and summary, history, learner profile, recommendations, memory | OK |
| Privacy | consent read and save, export, delete telemetry, delete session | OK |

Manual pass in the browser: sign-up, sign-in, Today, Library, Study (streamed cited answer),
Review, Progress, History and Settings all render with no console errors.

## Problems found

| # | Problem | Evidence | Severity | Status |
| --- | --- | --- | --- | --- |
| 1 | Static files are served without `Cache-Control`, so after an update the browser can run old HTML and JS against new code. | The browser kept a stale `index.html`; the active tab label became invisible until the cache was refreshed. | High | Fixed: `no-cache` plus ETag revalidation, with a test |
| 2 | A slide title that wraps onto two lines is cut to the first line. | Week 1 became the topic "Microprocessor &" instead of "Microprocessor & Computer Architecture". | Medium | Fixed, with JS tests; checked in the browser |
| 3 | `GET /student/{id}/learning_path` returns a fixed mathematics path (algebra, limits, derivatives) that has nothing to do with the learner's notes. The UI does not call it. | Journey response | Medium | Rebuilt from the learner's own topics, with 3 integration tests |
| 4 | `GET /sessions/{id}/summary` returns its summary as a JSON string inside JSON. | Journey response | Low | Fixed: always bullet points, with unit tests |
| 5 | After sign-up the email field is cleared, so the learner retypes it to sign in. | Browser | Low | Fixed; checked in the browser |
| 6 | A tutor question waits behind a running quiz or flashcard job and shows only "queued", with no reason given. | Browser, about 2 minutes | Low | Label fixed; the single model queue itself is unchanged |
| 7 | OCR is unavailable: Tesseract is not installed, so scanned PDFs and images cannot be read. | `/documents/capabilities` | Setup | Needs Tesseract on this machine |
| 8 | `phi3:mini` fails the quiz JSON schema and regenerates, which makes quizzes slow. | Server log | Known | Use `qwen2.5:7b` |

## Structure changes

- `shared/utils.py` was split into `shared/logging_setup.py`, `shared/text.py`,
  `shared/rate_limit.py` and `maintenance/health_check.py`. Helpers that nothing imported were
  removed.
- `ai/`: `parser` → `response_parser`, `models` → `response_models`, `history` →
  `conversation_history`, `nlp_engine` → `tutor_llm`, `streaming` → `stream_schema`.
- `emotion/routes.py` → `api/routes/emotion.py`.
- Browser views are named after their screens: `today.js`, `library.js`, `study.js` and
  `progress.js`. Route ids such as `#/dashboard` are unchanged, so saved links still work.
- The finished animation plans moved to `docs/project/plans/animation/`, and the 2026-11-02 data
  backup moved into the git-ignored `backups/`.

## Not covered yet (needs inputs)

- Text-based lecture PDF (only a syllabus PDF was available), Word `.docx` notes and `.txt` notes.
- Scanned PDF or image notes (OCR), after Tesseract is installed.
- Camera and emotion feature with a real camera (`uv run --extra camera sentio`, `ENABLE_EMOTION=true`).
