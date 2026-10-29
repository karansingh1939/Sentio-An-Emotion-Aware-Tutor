# Local model comparison - 29 October 2026

Four already-installed Ollama models were run through the same 12-case real HTTP
grounding test used on 12 October (`tests/fixtures/study_grounding_v1.json`): four
answerable questions, six asking for facts absent from the notes, and two ambiguous
questions. Each run uses a disposable runtime home, a fresh synthetic account,
real upload, selected-source retrieval and the production study path. No model was
downloaded.

| Model                         | Size | Answerable | Absent facts declined | Ambiguous | Absent facts answered | Source fallback | Median / max turn |
| ----------------------------- | ---: | ---------: | --------------------: | --------: | --------------------: | --------------: | ----------------: |
| `phi3:mini` (current default) | 3.8B |        2/4 |                   6/6 |       0/2 |                     0 |               0 |   16.6 s / 28.7 s |
| `qwen2.5:7b`                  | 7.6B |        3/4 |                   6/6 |       1/2 |                     0 |               2 |   24.3 s / 58.2 s |
| `llama3:latest`               | 8.0B |        3/4 |                   6/6 |       1/2 |                     0 |               1 |   28.5 s / 90.6 s |
| `llama3.2:latest`             | 3.2B |        0/4 |                   6/6 |       0/2 |                     0 |               4 |    9.3 s / 22.4 s |

Counts are lexical-rubric passes. "Source fallback" means generated output failed
validation and Sentio showed quoted passages instead; those are never counted as
answers.

## Reading the result

- `qwen2.5:7b` and `llama3` each answered one more covered question than `phi3:mini`
  and handled one ambiguous question, without answering any absent-fact question.
  `qwen2.5:7b` was faster and had a lower worst case than `llama3`.
- `llama3.2` was fastest but answered none of the covered questions.
- **Recommendation:** use `qwen2.5:7b` where about 5 GB of free memory is available;
  keep `phi3:mini` on low-memory machines. Switch with `OLLAMA_MODEL=qwen2.5:7b` in
  `.env` and restart Sentio. The shipped default stays `phi3:mini`.

## Limits

One run per case and model, 12 author-drafted synthetic cases, lexical rubrics only,
one machine (20 logical CPUs, about 16 GB RAM, under 3 GB free during the runs). A
one-question difference is not statistically meaningful, and the prompt was revised
on earlier failures from this dataset, so it is not a held-out estimate. Lexical
passes do not establish semantic correctness; review the actual replies with the
[author review guide](../guides/AUTHOR_REVIEW.md). A review page for the
`qwen2.5:7b` replies can be regenerated with:

```sh
uv run python scripts/eval/prepare_study_review.py --dataset tests/fixtures/study_grounding_v1.json --report reports/generation/model-compare-2026-10-29-qwen2-5-7b.json --output reports/evidence/review-study-2026-10-29-qwen2.5-7b.html
```

## Reproduce

```sh
uv run python scripts/eval/live_study_journey.py --grounding-dataset tests/fixtures/study_grounding_v1.json --model qwen2.5:7b --output reports/generation/new-compare.json
```

Raw reports, with every reply, timing and model digest:
[phi3:mini](../../reports/generation/model-compare-2026-10-29-phi3-mini.json),
[qwen2.5:7b](../../reports/generation/model-compare-2026-10-29-qwen2-5-7b.json),
[llama3](../../reports/generation/model-compare-2026-10-29-llama3-latest.json),
[llama3.2](../../reports/generation/model-compare-2026-10-29-llama3-2-latest.json).
