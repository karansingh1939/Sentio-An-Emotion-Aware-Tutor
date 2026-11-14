# Repeated semantic grading experiment — 2026-10-11

Problem: the existing local grader rejects some valid paraphrases. In particular,
"It stops the repeated calls" remains scored 0.5 for a recursion base-case question.
The previous evaluation used one run and too few contrasting cases.

Dataset v2.0 retains the 14 v1 cases and adds 14 contrasting rubrics. Of 28 cases,
two are exact matches and one is blank; those bypass model inference. The other
25 exercise semantic grading. Labels are synthetic, author-written and not
independently reviewed. The candidate was designed using observed v1 failures;
this is a development comparison, not an unbiased held-out accuracy estimate.

Experiment: three repeats of the production prompt and a candidate clarification
about essential meaning, complete paraphrases, numeric equivalents and
contradictions. Profile order alternates by repeat. Requests use fresh empty
history, temperature zero and the unchanged 512-output-token limit. Model:
`ollama/phi3:mini`, digest
`4f222292793889a9a40a020799cfd28d53f3e01af25d48e06c5e708610fc47e9`.
Hardware: Windows 11, Intel64 Family 6 Model 154 Stepping 3, 20 logical CPUs,
approximately 15.70 GiB RAM. Dataset hash, exact prompts and individual scores
are saved in [the JSON report](grading-comparison-2026-10-11.json).

| Profile | Semantic rubrics passed in each repeat | False positives per repeat | False negatives per repeat | Total rubrics passed per repeat |
|---|---:|---:|---:|---:|
| Production baseline | 20/25, 20/25, 20/25 | 2 | 3 | 23/28 |
| Candidate clarification | 20/25, 20/25, 20/25 | 0 | 5 | 23/28 |

Both profiles passed all exact/blank checks. No malformed-output errors occurred.
The baseline wrongly accepted an incorrect percentage magnitude and a heat-flow
answer missing the destination. The candidate rejected those but newly rejected
a valid recursion paraphrase and the standard force-unit abbreviation `N`.
Both retained the original base-case paraphrase failure. Repeats gave identical
outcomes on this machine; that is an observation, not statistical independence.

A second, single targeted probe placed question, reference and answer together
in the user message with a shorter scoring instruction. It improved some
abbreviation/numeric cases but still rejected the original paraphrase and
accepted the incomplete heat-flow answer. This eight-case diagnostic was not
promoted to a full comparison. Its prompt and results are retained in
[the probe report](grading-context-probe-2026-10-11.json).

Decision: do not adopt either prompt. The repeated candidate did not increase
rubric passes and traded valid-answer acceptance for stricter rejection. Keep
strict schema validation and retry errors; do not lower the passing threshold
or add phrase-specific exceptions to make the dataset pass. Production semantic
grading remains fallible. A stronger local model and independently reviewed
rubrics are better next experiments than claiming a successful prompt fix.

Reproduce the repeated comparison:

```powershell
uv run python scripts/eval/evaluate_grading.py --repeats 3 --output reports/grading-comparison.json
```

Measurements use local Ollama only and no learner data.
