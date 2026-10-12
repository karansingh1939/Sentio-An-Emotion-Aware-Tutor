# Local CPU generation experiment

Two installed models were compared on three identical authored cases: a direct
physics question, a paraphrase, and an ethanol boiling-point question absent from
the physics passage. Each case ran three times in both cold and warm conditions.
There were 18 requests per model per prompt policy, 72 requests altogether.
No models were downloaded. Raw outputs, digests, hardware, Ollama version,
configuration, prompt hashes and per-request timings are in the reports.

## Measured results

All times below are median seconds. First visible means the first safe character
in the JSON text field; these measurements exclude retrieval, HTTP application
processing and browser rendering. Cold means unloading and reloading Ollama's
model; operating-system file caches were not cleared.

| Policy | Model | Cold first / complete | Warm first / complete | Valid schema, cold / warm |
|---|---|---|---|---|
| Original | phi3:mini | 17.129 / 32.476 | 0.966 / 15.907 | 9/9, 9/9 |
| Original | qwen2.5:0.5b | 3.992 / 4.715 | 0.227 / 1.417 | 9/9, 9/9 |
| Explicit grounding | phi3:mini | 19.101 / 35.667 | 0.995 / 20.295 | 9/9, 6/9 |
| Explicit grounding | qwen2.5:0.5b | 4.361 / 5.170 | 0.241 / 0.982 | 9/9, 9/9 |

Reports: [original prompts](../reports/generation/compare-cpu-v1.json) and
[grounding prompts](../reports/generation/compare-grounding-v2.json).
The historical reports predate the prompt-policy metadata field. Their hashes
are verified against the corresponding legacy/grounding reconstruction by a
regression test; original measurements have not been rewritten.

## What failed, and the product decision

Both models supplied ethanol temperatures absent from the notes. In the original
experiment phi3 supplied 78.37 C with an unrelated forces.txt citation, while Qwen
supplied 110.1 C without a citation. With explicit grounding instructions, both
still supplied outside information. Phi's unrelated citation persisted. Three
warm phi outputs reached the 256-token limit and failed final validation.

JSON validity and membership in the retrieved citation list do not prove factual
support. The lexical rubric is a limited regression signal, not an accuracy
score, and is not suitable for selecting a release model. Qwen is faster here
but fails the grounding cases; phi3 remains the baseline, not a validated winner.
Prompt instructions alone did not solve unsupported acceptance.

The product now refuses generation when selected notes have no retrievable
relevance signal, instead of silently switching to built-in curriculum. The
current gate uses substantive term overlap or a raw cosine threshold of 0.35.
This is an exploratory heuristic, not a calibrated probability. It can still
accept passages that mention the topic without containing the answer. Its
answerable-question coverage and unsupported acceptance require held-out review.
The offline raw-hybrid baseline currently precedes this product gate; a future
adoption experiment must compare against the actual gated product baseline.

A separate real HTTP journey exposed an uncited generated answer rejected by
final validation. [The first run](../reports/generation/live-journey-v1.json)
records the failure. Deterministic browser and persistence tests must not be
substituted for live-model acceptance. The journey script preserves unsuccessful
streams from its authored disposable account and retries no rejected answer as
though it had succeeded.

Further live runs isolated another failure: a request for one quiz question
returned five, including invalid choice options. The generation schema now fixes
both minimum and maximum item counts to the learner's request, and server-side
validation rejects wrong counts before publication. This uses inherited dynamic
models as described in [Pydantic's documentation](https://docs.pydantic.dev/latest/concepts/models/#dynamic-model-creation).
The failed [second](../reports/generation/live-journey-v2.json) and
[third](../reports/generation/live-journey-v3.json) runs are retained. After the
constraint, the [fourth run](../reports/generation/live-journey-v4.json) completed
upload, cited explanation, insufficient evidence, quiz generation/submission,
cards/review, preferences, task completion, restart and saved-work/token checks.
One complete run demonstrates mechanics on this fixture, not consistent model
quality. Earlier failures remain relevant. Final validation also rejects a
provider's output-limit termination even if its prefix happens to be valid JSON.

## Reproduce

Start your already-installed Ollama models. Use a new report path each time:

```powershell
uv run python scripts/benchmark_ollama_cpu.py --models phi3:mini qwen2.5:0.5b --prompt-policy legacy --repetitions 3 --output reports/generation/new-legacy.json
uv run python scripts/benchmark_ollama_cpu.py --models phi3:mini qwen2.5:0.5b --prompt-policy grounding --repetitions 3 --output reports/generation/new-grounding.json
uv run python scripts/live_study_journey.py --output reports/generation/new-journey.json
```

The live journey uses an isolated temporary home and database, a generated local
signing key and a synthetic account. It tests restart persistence with the same
token. It copies generated reference answers only to exercise grading mechanics;
it does not demonstrate student learning or independently verify quiz correctness.

The comparison uses CPU inference, a 2048-token context, 256 output tokens,
temperature zero and seed 42. These are benchmark settings, not all production
defaults. Results are limited by three short cases, repeated question wording,
sequential model order, thermal/background-load effects and no independent
rubric review. Reported Ollama allocation is not peak process RAM. A broader
grounded evaluation and manually reviewed evidence labels are still release gates.

The candidate's upstream documentation records its packaging and licence:
[Ollama tag](https://ollama.com/library/qwen2.5:0.5b),
[Qwen model card](https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct).
Streaming/schema contracts follow the [Ollama chat API](https://docs.ollama.com/api/chat).
The experiment runner, failure analysis and product guards are repository work;
the generation models and inference engine are upstream components.
