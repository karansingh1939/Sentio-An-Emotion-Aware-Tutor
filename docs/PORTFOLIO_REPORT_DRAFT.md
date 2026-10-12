# Sentio: evidence support for a local study tutor

Status: implementation and experiment draft. A trained evidence model and
independent learning validation are not complete.

## Problem and hypothesis

Local language models can produce plausible answers when a learner's selected
notes do not contain the answer. An available filename citation does not make
that answer supported. The research question is whether a lightweight learned
passage-support classifier can reduce unsupported acceptance without decreasing
answerable-question coverage or exceeding the retrieval budget.

The product connects notes, cited tutoring, quizzes, flashcards, due review and
daily planning. Reliability matters because a misleading answer, lost upload or
duplicated review changes the learner's experience even when a model benchmark
looks good.

## Dataset and original component

The versioned corpus contains 30 short original, AI-assisted notes across ten
academic topics and 120 questions. Topic/source-disjoint splits allocate six
topics to training and two each to validation and test. Manifests freeze content
and test hashes. The question–passage matrix has 1,584 pairs. The notes are
synthetic academic material, not learner uploads or an independently sampled
student dataset.

Labels remain unreviewed. The offline review page shows the question and passage,
gives sufficiency examples, accepts rationale and reviewer identity, supports
skipping uncertain pairs and exports receipts. A saved reviewer name does not
prove independent review. Training refuses incomplete, stale or unreviewed
annotations. See the [dataset and experiment card](EVIDENCE_EXPERIMENT.md).

The implemented training recipe uses standardized, class-balanced logistic
regression with embedding similarity, keyword score, substantive overlap, query
and passage lengths, retrieval rank and candidate score gap. Development data
selects regularization, calibration and threshold; frozen test data is reserved
for final reporting. Feature ablations and uncertainty estimates are implemented.
No real classifier has been trained on reviewed labels, and no accuracy or
calibration improvement is claimed.

## Existing evidence and failed experiments

The generation study used two already-installed models, identical prompts and
three authored cases with repeated cold/warm CPU measurements. Qwen was faster
but both models answered an unsupported question. Explicit grounding instructions
did not prevent this; phi sometimes cited an unrelated passage. Three outputs in
one warm condition reached the benchmark token limit.

Real HTTP journeys also found an uncited answer and an invalid quiz batch. Exact
count constraints and final validation now prevent wrong-sized batches from
being published. The fourth isolated journey completed notes → cited answer →
unsupported response → quiz → cards → review → restart. This is one mechanics
demonstration, not a teaching-quality estimate. The failures, measured table,
commands and limits are in [the generation report](LOCAL_GENERATION_EXPERIMENT.md).

The current relevance gate is a heuristic. It is not the proposed learned model,
and raw cosine similarity is not a correctness probability. The original
offline hybrid baseline must be brought into parity with the current product
gate before any model adoption comparison.

## Engineering contribution and attribution

Repository work includes the study UI, owner-scoped context and jobs, recoverable
document publication, streaming cancellation and receipts, atomic practice/review
persistence, deterministic planning, backups/migrations, corpus/review tooling,
CPU experiment runner and failure analysis. Coding and corpus drafting used AI
assistance; this must be disclosed in a course submission.

FastAPI, Pydantic, SQLite, Qdrant, Sentence Transformers, scikit-learn, Ollama,
upstream generation/embedding models, MLflow, Playwright and Pillow are upstream
components. No full LLM training was performed. A pretrained cross-encoder
implementation is reused, but its weights were unavailable locally during the
recorded extraction and were not downloaded. Camera heuristics are experimental
and not an original validated emotion model for this study.

## Completion gates and presentation

Finish manual evidence review, repeat independent checks where possible, compare
all available retrieval baselines, train/calibrate the original classifier and
publish results even if it fails the adoption gate. Adopt only with reduced
unsupported acceptance, preserved answerable coverage and measured latency within
budget. Add broader source/ambiguous-question and repeated live generation tests.
Independent label review and actual learning studies remain later validation.

For a demonstration, show one selected-note explanation, an unsupported question,
source-based practice, review and restart. Explain a retained failure before
describing the fix. Use the [architecture and sequence diagrams](ARCHITECTURE.md)
and exclude credentials, learner uploads and personal records.

Defensible résumé drafts for the work completed so far:

- Built a local study application with authenticated document tutoring, durable
  jobs, cancellable streaming, transactional review schedules and verified restart
  persistence.
- Designed a frozen 30-document, 120-question evidence corpus and a CPU classifier
  experiment pipeline with review receipts, leakage checks, calibration and
  feature ablations; training results pending manual annotation.
- Ran 72 controlled local-generation requests and retained grounding failures;
  used live workflow failures to enforce output counts and final validation.

Do not add model accuracy gains, adoption claims, user counts or learning outcomes
until those values have been measured and supported by the corresponding reports.
