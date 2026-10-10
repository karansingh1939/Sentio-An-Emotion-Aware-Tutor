# Measured AI evaluation ? 2026-10-11

Problem: the old benchmark retrieved without authenticated learner ownership or
selected documents, scanned real folders, and fabricated answer-quality scores.
Its numbers were not evidence of grounded retrieval.

Experiment: dataset v1.0 contains 12 author-written short documents, 18 answerable
or paraphrased/adversarial-source retrieval questions, four negative questions,
and 14 grading rubrics. Each retrieval mode gets a new temporary SQLite database,
an actually registered/logged-in learner, selected owned document IDs and an
in-memory vector store. Relevant chunk IDs are resolved from indexed source text.
Model loading and ingestion are excluded from query latency. No learner data is
read or modified. Corpus provenance is synthetic and not expert-reviewed.

| Mode | Document hit rate | Recall@5 | MRR | Mean query latency | Negative candidate rate |
|---|---:|---:|---:|---:|---:|
| keyword | 0.9444 | 0.9444 | 0.9444 | 0.54 ms | 75% |
| hybrid | 0.9444 | 0.9444 | 0.9444 | 10.10 ms | 75% |

Both modes found the relevant passage in 17 of 18 positive cases. Hybrid search
showed no gain on this small corpus and took more query time. Three of four
negative questions returned candidates in both modes. Candidate return is an
abstention diagnostic, not a hallucination measurement: this experiment does
not generate tutor answers. Adversarial source inclusion only exercises retrieval,
not proof that the tutor resists prompt injection.

Decision: keep both retrieval modes available; do not claim hybrid superiority
or change production ranking from this small experiment. Next evaluation should
use longer sources, ambiguity, multiple relevant passages, and independent labels.

## Quiz grading

The first run used the previous prompt and default provider temperature (0.7).
Exact matches passed 2/2 deterministic cases; semantic grading passed 10/12
rubrics. One response contradicted the score threshold and was safely rejected
by validation. An adversarial answer asking to be marked correct was accepted.

The revision moves student text into JSON user data, defines instruction boundaries
in the system prompt, uses temperature 0, and rejects empty answers deterministically.
The second run passed 2/2 exact cases and 11/12 other rubric cases. The attack case
was rejected, but g05 (an equivalent description of a recursion base case) was
incorrectly scored 0.5. Thus the model can still reject valid wording. The prompt
and temperature both changed; this experiment cannot isolate their causal effects.
These single runs are observations, not statistically established accuracy.
Blank-answer handling is deterministic and is counted in the rubric group without
claiming it measures model performance.

Decision: retain strict schema validation and honest retry errors. Keep exact
answer tests separate from model experiments. Do not silently convert unavailable
or invalid model responses to guessed grades. Human-reviewed labels and repeated
runs are the next step before any high-stakes grading use.

## Reproduction and configuration

```powershell
uv run python scripts/evaluate_retrieval.py --grade --output reports/evaluation.json
```

Hardware: Intel64 Family 6 Model 154 Stepping 3, GenuineIntel; 20 logical CPUs; 15.70 GiB RAM; Windows-11-10.0.26200-SP0.

Embedding: `all-MiniLM-L6-v2` on CPU, 500-character chunks with 100-character overlap, top 5, vector/keyword weights 0.75/0.25. Model must be cached locally; vector indexing failure aborts the hybrid experiment.

Grader: `ollama/phi3:mini`, digest `4f222292793889a9a40a020799cfd28d53f3e01af25d48e06c5e708610fc47e9`, temperature 0 after the revision, default 512 output-token limit. Exact-answer and blank-answer cases bypass the model. Package versions and dataset SHA-256 (`a979098d33f912da9440f14d71bb64dd7cf0935d8afe97f00fabd9412fd51763`) are recorded in JSON. The before-run file predates extended metadata recording; it retains its original measured values.

Raw evidence: [before](evaluation-before-2026-10-11.json),
[after](evaluation-after-2026-10-11.json), and the
[versioned dataset](../tests/fixtures/evaluation_v1/dataset.json).

Emotion recognition remains **unverified**: successful loading or a working webcam
pipeline does not establish accuracy without an appropriate labelled dataset.
No training, paid services, synthetic commit dates, or guaranteed accuracy claims
were introduced.
