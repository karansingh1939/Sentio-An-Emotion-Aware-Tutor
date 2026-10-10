# Development record

## 2026-10-11 ? Working baseline

Problem: a partial package migration left build/test setup inconsistent and study
flows had persistence, grounding, privacy, and rendering failures.

Changes: completed the validated `src`/uv layout and repairs documented in
[the repair report](FIX_REPORT_2026-10-11.md). Preserved upstream history and MIT
attribution. Learner data, credentials, model weights, and generated output remain
excluded from new commits.

Evidence: 131 Python tests plus 31 subtests, four JavaScript scripts, clean Ruff
and Prettier checks, successful wheel/source build, and a real local Ollama chat.
Docker, hosted CI, and a physical webcam were not verified.

Publication: intended private repository is
`karansingh-1939/Sentio-An-Emotion-Aware-Tutor`. Account authentication is required
before creation/push. The cached Git credential belongs to `karansingh1939`, a
different account; it will not be used to publish to the requested destination.

Next: replace simulated retrieval scores with a versioned isolated benchmark.
