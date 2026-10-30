# Interview guide

A one-minute pitch, the six things worth explaining, and the questions they invite.
Every claim here links to code, a test or a measurement in this repository.

## Pitch

> Sentio is a local AI study tutor. You upload your notes, and it answers questions
> only from them, with page citations. If the notes don't cover a question, it refuses
> instead of guessing. The same notes become quizzes and spaced-repetition flashcards.
> I built the retrieval pipeline with an evidence gate, made the model's structured
> output reliable, and compared four local models to choose one on measured results.

## Talking points

| Topic                | What to say                                                                                                                                                                                                                                                                                                     | Show                                                                              |
| -------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------- |
| RAG pipeline         | Notes are chunked (500 chars, 100 overlap) and indexed twice: BM25 for exact terms and MiniLM embeddings in Qdrant. A hybrid score (0.75 dense + 0.25 keyword) ranks owner-scoped chunks.                                                                                                                       | `src/sentio/rag/knowledge_base.py`, `src/sentio/rag/reranker.py`                  |
| Evidence gate        | The LangGraph workflow always retrieves first. If no retrieved passage has a relevance signal (no keyword match and no dense score above the threshold), the `refuse` node answers without calling the model. When some passage is retrieved, declining is left to the model, which the prompt instructs.       | `src/sentio/tutor/orchestrator.py`, `tests/unit/test_study_prompt_boundaries.py`  |
| Structured output    | The model must return JSON matching a schema. Invalid replies are repaired or regenerated (up to twice), citations must reference retrieved passages, and only then does it fall back to quoted passages. This fixed `qwen2.5:7b` quizzes, which had failed on every request.                                   | `src/sentio/ai/structured_parser.py`, `tests/integration/test_practice_repair.py` |
| Model evaluation     | A 12-case grounding test over real HTTP: 4 answerable, 6 absent facts, 2 ambiguous. `qwen2.5:7b` answered 3/4 covered questions vs 2/4 for `phi3:mini`; all models declined 6/6 absent facts. Those refusals were written by the models: each case retrieved some passage, so the gate itself did not fire.     | `docs/evaluation/MODEL_COMPARISON_2026-10-29.md`                                  |
| Syllabus progress    | The syllabus is parsed into units and topics, each matched to lecture topics by weighted word overlap (live, so new lectures count), with learner corrections stored. Status rolls up from topic mastery, giving a course percentage and a list of syllabus topics the notes don't cover yet.                   | `src/sentio/study/syllabus.py`, `tests/integration/test_syllabus_progress.py`     |
| Topic mastery        | Topics are page ranges from slide titles. Practising a topic quizzes on exactly its slides. The model names each question's slide and the server checks it against word overlap (on a real lecture, 17 of 17 named slides passed and 15 of 17 agreed exactly with the overlap guess), and each answer stores its question id, so a topic's state (Not started / Practising / Ready: the last 3 answers all correct) is a join, not a guess. Weak topics link back to slides. | `src/sentio/study/topics.py`, `tests/integration/test_topic_mastery.py`           |
| Spaced repetition    | FSRS-5 replaces SM-2. Each card has stability (days until recall drops to 90%) and difficulty; recall decays as a power curve and each rating updates both with the published parameters. The same recall probability feeds the Progress forgetting risk.                                                       | `src/sentio/flashcards/fsrs.py`, `tests/unit/test_fsrs.py`                        |
| Reliability          | Long work runs as durable background jobs; answers stream and can be stopped; request receipts make retries idempotent; saves re-check the study context (notes, goal) in one transaction and reject stale work.                                                                                                | `src/sentio/tutor/stream_service.py`, `src/sentio/jobs/service.py`                |
| Fair difficulty      | Difficulty is what the learner chose. It moves one step only on an explicit request (matched as a phrase to the tutor, so "Why is diamond harder than graphite?" changes nothing) or a quiz streak (3 right up, 2 wrong down). Every change is shown with its reason and an Undo that pins the level.           | `src/sentio/tutor/difficulty.py`, `tests/integration/test_fair_difficulty.py`     |
| Emotion side feature | My earlier FER2013 CNN and browser attention tracking, kept as an opt-in feature: off by default, consent checked on the server, frames size-limited, and it only changes the tutor's tone.                                                                                                                     | `src/sentio/emotion/`, `docs/guides/EMOTION.md`                                   |

## Questions to expect

- **Why local models?** Privacy (notes never leave the machine) and zero cost. The
  trade-off is latency: 15–60 s per answer on CPU.
- **How do you know answers are correct?** I don't claim that. Citations prove which
  passage was used, the evidence gate prevents unsupported answers, and correctness is
  measured with the grounding test and a human review of real replies.
- **Why SQLite and not Postgres?** One user, one process, zero setup. Qdrant is only an
  index that can be rebuilt; SQLite is the source of truth. Multi-user hosting would
  need Postgres and a shared job queue.
- **Why FSRS instead of SM-2?** SM-2 uses fixed rules and an ease factor; FSRS is a
  model of memory with parameters fitted on large public review logs, and it gives a
  recall probability I can reuse. Next step: fit the parameters on my own review history.
- **What would you improve next?** A trained evidence classifier once labels are
  reviewed, a larger held-out evaluation set, and a cross-encoder re-ranker comparison.
- **What was hard?** Making generation reliable on small local models: they break JSON,
  omit fields and invent citations. The schema, repair loop and evidence gate exist
  because of failures recorded in the reports.

## Demo in five minutes

1. `uv run sentio --port 8001`, sign up, create a course in Library and upload two lecture decks at once.
2. Ask a question the notes answer: point at the citation.
3. Ask something the notes don't cover: show the refusal.
4. Make a quiz, open **Edit this question**, show the provenance label.
5. Open `docs/evaluation/MODEL_COMPARISON_2026-10-29.md` and explain the model choice.
