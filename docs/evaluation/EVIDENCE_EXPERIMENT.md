# Passage-support experiment

Status: the experiment pipeline is implemented; the corpus and all labels await
human review. No trained-product improvement or academic correctness is claimed.
The tutor continues to use its baseline retrieval behavior.

## Dataset card

`datasets/evidence_v1/corpus.json` contains 30 original AI-assisted short notes,
three per academic topic, and 120 drafted questions: direct, paraphrased,
ambiguous and absent-evidence cases. Text is original project material under the
repository's MIT licence. It includes no learner uploads, credentials or personal
records. These drafts need academic review before use as course material.

The frozen manifest records the corpus and test hashes. Six topics train the
classifier; optimization/statistics provide development data; machine learning
and operating systems form the untouched test topics. Source documents, variant
groups and near-duplicate text cannot cross splits. Each split retrieves only
its own corpus to maintain source disjointness. This small-corpus setup is not a
large-library benchmark. A reviewed subsequent version should add longer notes,
natural student questions and more difficult within-topic negatives.
Drafted missing-result questions can make abstention unusually easy and teach
wording shortcuts. Question-kind slices and feature ablations help expose this;
they do not replace evaluation on natural student questions.

Each question has a pair with every passage in its split: 1584 pairs. This complete
coverage permits a recall denominator derived from reviewed labels, rather than
counting only passages a particular retriever happened to find. The generated
proposal is never ground truth. Annotation review hides it.

## Label rubric and review

Label **1** only when the passage alone contains enough information for a complete
answer, with straightforward paraphrase or arithmetic allowed. Label **0** for a
related passage that misses a necessary fact, requires outside knowledge, or
cannot resolve an ambiguous referent. Record the exact supporting statement or
what information is missing. A question's answerability is derived from whether
any reviewed passage supplies sufficient evidence. Reassess the question if this
differs from its drafted kind; the draft is not authoritative.

Record reviewer identity and rationale. The annotation binds to a hash of both
texts. Stale annotations, duplicates, incomplete labels and anonymous review are
rejected before fitting. A named receipt is an audit trail, not proof that a person
actually read the passage. Author review must not be described as independent
ground truth. Independent reviewers and agreement measurements are future work.

Generate a readable keyword annotation preview without loading models:

```powershell
uv run python scripts/eval/evidence_experiment.py prepare --keyword-only --output datasets/evidence_v1/annotation-preview.json
uv run python scripts/eval/evidence_experiment.py review --features datasets/evidence_v1/annotation-preview.json --annotations datasets/evidence_v1/annotations-author.json --reviewer "Your name" --split train
```

Repeat review for validation and test. Each decision saves immediately; `s` skips
a pair and `q` exits. Preview/features/annotations stay ignored by Git by default.
Freeze a new corpus version instead of overwriting the existing manifest.

For a browser interface with examples, progress recovery, small batches, skip and
download/import, use:

```powershell
uv run python scripts/eval/evidence_experiment.py review-page --features datasets/evidence_v1/annotation-preview.json --output reports/evidence/review-v1.html
```

Open `reports/evidence/review-v1.html`. Read one question and passage at a time.
“Enough evidence” means you can answer using only that text; “Missing evidence”
means a necessary fact or clear referent is absent. “Unsure” creates no label.
Enter a reviewer name and a short explanation for each saved decision. Start with
ten decisions, then download `annotations-author.json`. Copy the downloaded file
to the annotations path used in the training command. It can also restore progress
in another browser. Conflicting reviewer files stay separate for disagreement
review. No proposed AI label is displayed.

## Model card and reproducible runs

Target event: **passage supplies sufficient evidence**, not probability that a
generated tutor answer is correct. Seven features: embedding similarity, BM25
score, query overlap, query/passage lengths, hybrid rank and best-score gap.
Features never contain the proposed or reviewed label.

The CPU feature collector reuses `BM25Searcher`, `HybridRanker` and the existing
`CrossEncoderReranker`. Models load only from the local cache. Missing embedding
weights fail preparation; missing cross-encoder weights produce an explicit
unavailable comparison and recorded failure. Models are never downloaded
automatically. Weight hashes,
package versions, platform, observed process RSS and measured warm-query timings
are recorded. RSS is not peak memory. Model loading/index construction and the
production Qdrant path require separate measurements.

```powershell
uv run python scripts/eval/evidence_experiment.py prepare --output datasets/evidence_v1/features-cpu-v1.json
uv run --extra experiments python scripts/eval/evidence_experiment.py train --features datasets/evidence_v1/features-cpu-v1.json --annotations datasets/evidence_v1/annotations-author.json --output reports/evidence/run-001
```

Training refuses keyword-only previews and unreviewed labels. The CLI does not
touch accounts, uploaded notes, learner sessions or the production vector store.
Experiment output directories are immutable. Install experiment dependencies only
for offline work; MLflow is optional and absent from application startup.

Class-balanced logistic regression fits on standardized training features.
Candidate C values are 0.01, 0.1, 1 and 10. One development topic calibrates an
already-fitted classifier; the other selects regularization/calibration and gates.
Sigmoid calibration uses scikit-learn's `FrozenEstimator`, following its
[calibration guidance](https://scikit-learn.org/stable/modules/calibration.html).
Scaling is fitted on training rows only. Question variants remain grouped.

Compare keyword, dense, existing hybrid, hybrid's top ten reranked by the existing
cross-encoder, and the learned support score. Baseline thresholds maximize
development support F1; ties favor lower unsupported acceptance. A learned
threshold qualifies only when it reduces unsupported acceptance while maintaining
answerable coverage against tuned hybrid on development data. Configuration is
fixed before test scoring. Test performance never selects C or calibration.

Reports include Recall@5, MRR, nDCG@5, question coverage, accepted unsupported
questions, rejected answerable questions, accepted answers without passage support,
pair precision/recall, Brier score, reliability-bin values, baseline query timings,
classifier prediction timing and feature ablations. Bootstrap intervals resample
questions; related variants and just two test topics limit their interpretation.
They are exploratory intervals, not evidence of broad domain generalization.

Append `--mlflow` to the training command for local experiment tracking:

```powershell
uv run --extra experiments python scripts/eval/evidence_experiment.py train --features datasets/evidence_v1/features-cpu-v1.json --annotations datasets/evidence_v1/annotations-author.json --output reports/evidence/run-002 --mlflow
```

Tracking records hashes, selected configuration, metrics and report artifacts using
[MLflow's local tracking API](https://mlflow.org/docs/latest/ml/tracking/). Its service
does not run with the product. The trained artifact is a trusted local experiment
file, never automatically loaded from an upload.

## Adoption and attribution

Offline quality alone does not authorize adoption. `adoption.eligible` remains
false until real retrieval stays within 300 ms and grounded generation is reviewed.
Otherwise keep the baseline and publish the failed experiment honestly. Citation
support, first-visible answer latency, cold-start memory, student learning effects
and independent label review are separate evaluations still required.

Original project additions: experiment formulation, corpus drafts, split/label
contracts, feature integration, comparisons, calibration and adoption policy.
Upstream components: scikit-learn, Sentence Transformers, its pretrained embedding
and cross-encoder models, existing Sentio BM25/hybrid retrieval, Ollama and MLflow.
Do not claim upstream model training or invent accuracy, user counts or gains.
