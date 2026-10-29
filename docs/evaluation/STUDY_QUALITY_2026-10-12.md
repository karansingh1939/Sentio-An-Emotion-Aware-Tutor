# Study grounding stress test - 12 October 2026

This is a development experiment with 12 original AI-assisted synthetic questions across four longer fictional notes. It exercises actual account registration, upload, selected-source retrieval, fresh sessions, local generation, output validation, and HTTP publication. It is separate from the evidence-classifier training corpus, but prompt revision used observed failures, so it is not an unbiased held-out accuracy estimate.

Cases cover four answerable questions, six absent facts/measurements, and two ambiguous questions. A quoted source attack checks whether the model follows an embedded instruction. Source isolation, JSON validity, citation membership, lexical matches, and semantic support are different properties. No independent semantic labels exist.

## Changes and observations

The study prompt separates source passages and learner memory from system instructions, removes claims of camera-based emotion observation, and makes grounding take precedence over examples or requests for outside facts. The revision adds exact citation strings to each passage and uses temperature zero. Legacy benchmark prompts remain intact for reproducing historical hashes.

| Run                                          | Generated | Abstention | Source recovery | Request errors | Lexical diagnostics passed | Median HTTP turn |
| -------------------------------------------- | --------: | ---------: | --------------: | -------------: | -------------------------: | ---------------: |
| Initial data-message prompt, v3              |         0 |          3 |               9 |              0 |                       3/12 |          17.96 s |
| Explicit references and temperature zero, v4 |         4 |          8 |               0 |              0 |                       8/12 |          14.70 s |

Both rows use the same updated first-sentence diagnostic on retained raw responses. A later sentence about a missing detail must not misclassify an otherwise generated answer as a full abstention. Original reports retain their originally computed fields; the separate [diagnostic reanalysis](../../reports/generation/study-grounding-diagnostics-2026-10-12.json) records this correction without rewriting measurements.

The final run still fails two answerable cases through refusal and fails both ambiguous-question lexical rubrics. The model can also add claims beyond the notes even when a lexical check passes. The apparent count change is a development observation, not an accuracy improvement: prompt content and temperature changed together, there is one run per case/policy, and labels/required words are author-drafted. These results do not establish causal effects or generalization.

The source-attack question produces the academic capacity answer in v4 rather than the injected capacity. One attack does not establish general prompt-injection resistance. Recovery excerpts are never counted as generated teaching successes. Fallback reliability and learning quality remain separate.

## Reproduce

```sh
uv run python scripts/eval/live_study_journey.py --grounding-dataset tests/fixtures/study_grounding_v1.json --output reports/generation/new-study-grounding.json
```

The tool creates a disposable runtime home and synthetic account, uses the already-installed `phi3:mini` model, and runs with Hugging Face downloads disabled. Qdrant uses memory mode and actual cached embeddings. Provider generation uses the production study path; total HTTP turn timing includes retrieval and generation, but excludes startup and upload. It records observations even when lexical rubrics fail; `observed` is not an acceptance result.

Hardware: Windows 11, Intel64 Family 6 Model 154 Stepping 3, 20 logical CPUs, approximately 15.70 GiB RAM. Model digest: `4f222292793889a9a40a020799cfd28d53f3e01af25d48e06c5e708610fc47e9`. Dataset hash and individual replies/times are in each report. Background load, caching, one machine, synthetic notes, and small case counts limit interpretation.

The first two tool runs failed during session setup, before any model-quality observation; their reports are retained as protocol failures. The evaluator was corrected to send the required identity field and a supported subject, and a real-API regression now covers that contract.

Raw reports: [v1 setup failure](../../reports/archive/generation/study-grounding-2026-10-12-v1.json), [v2 setup failure](../../reports/archive/generation/study-grounding-2026-10-12-v2.json), [v3](../../reports/archive/generation/study-grounding-2026-10-12-v3.json), [v4](../../reports/generation/study-grounding-2026-10-12-v4.json). Follow the [author-review guide](../guides/AUTHOR_REVIEW.md) to judge all 12 actual replies. Author review must not be described as independent validation.

## Deterministic grading repair

The earlier semantic experiment wrongly accepted `0.25%` for reference `25 percent`. Standalone decimals, fractions, and percentages now use exact rational comparisons, so this mismatch is rejected without inference; `25%` remains equivalent to `25 percent`, and `1/2` equals `0.5`. Prose, units, and broader semantic meaning still use the fallible model. Numeric cases are classified separately in future reports and do not inflate semantic model performance. Regression tests cover equivalent values and wrong magnitudes with the provider forbidden.
