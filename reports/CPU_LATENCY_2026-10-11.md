# Local CPU latency experiment ? 2026-10-11

Problem: the old benchmark appended previous responses to one live session and
used retrieval without owner/source selection. Later requests were longer and
incomparable. It estimated tokens instead of recording provider token counts.

Experiment: four profiles, three answerable questions from dataset v1.0, three
warm repetitions per question/profile, plus one separately recorded model-reload
cold request per profile. Every request reconstructs independent messages with
identical source, question and scripted history. Previous outputs are never
appended. Profile order rotates each repetition. This measures provider inference,
not end-to-end tutoring. Requests force CPU (`num_gpu=0`), seed 42, temperature 0.
Raw JSON records prompts, outputs, exact provider token counts, load time and
completion reason, including every failed rubric check.

| Profile | Changed control | Cold request | Median warm | Mean warm | Rubric passes |
|---|---|---:|---:|---:|---:|
| baseline | Production system prompt; 6 scripted turns; 1024-token cap | 35.26 s | 15.20 s | 15.45 s | 8/9 |
| short_prompt | Compact system prompt only | 13.78 s | 6.62 s | 7.48 s | 0/9 |
| short_history | 3 scripted turns only | 31.96 s | 14.53 s | 13.81 s | 6/9 |
| token_limit | 256-token cap only | 38.01 s | 14.41 s | 14.04 s | 6/9 |

The compact prompt is faster but omitted required citations in the observed
outputs (0/9 passes). Its sample factual answer was plausible; lack of citations
still fails this grounding rubric. Shorter history and the lower token cap passed
6/9 checks versus baseline 8/9. Several misses were uncited heat-transfer answers.
The lexical rubric requires valid JSON, the reference support phrase and filename
in `text`; it can reject valid paraphrases and is not semantic accuracy scoring.
All observed completion reasons were `stop`, so the 256-token cap did not show
truncation in these runs. That does not establish safety for complex answers.

Decision: **adopt none of these generation optimizations yet**. The measured
quality checks fell below baseline, and this sample is too small to justify
changing production prompts, history or output limits. Keep the unsuccessful
experiments as evidence. The next experiment needs an independent semantic
rubric, more question types and a quiet machine before drawing causal conclusions.

Engineering improvement shipped independently: chat now has a 200 second browser
deadline for the provider's 180 second request timeout, visible generation status,
duplicate-send protection and actionable provider errors. Generated study tools
allow longer deadlines because they may make multiple model requests. These UX
changes do not claim an inference speedup.

## Reproduce

```powershell
uv run python scripts/benchmark_ollama_cpu.py --repetitions 3 --cases 3 --output reports/latency.json
```

Hardware: Intel64 Family 6 Model 154 Stepping 3, GenuineIntel; 20 logical CPUs; 15.70 GiB RAM; Windows-11-10.0.26200-SP0. Model `phi3:mini`, digest `4f222292793889a9a40a020799cfd28d53f3e01af25d48e06c5e708610fc47e9`. The active Ollama model reported zero VRAM during the experiment.

Limitations: synthetic short sources and scripted history, only three questions,
three warm repetitions and one cold sample per profile. Cold means an Ollama
model unload/reload; OS file caches are not cleared. Some checks/builds ran on
the same local machine during collection, so background load can confound timing.
Prompt-prefix caching is a real part of these warm measurements. Seed and zero
temperature do not guarantee identical outputs across loads/provider versions.
The suite does not alter learner sessions or uploads and uses no paid services.

Evidence: [raw measurements](latency-2026-10-11.json),
[dataset and rubrics](../tests/fixtures/evaluation_v1/dataset.json), and
[Ollama's official chat API](https://docs.ollama.com/api/chat) documenting provider
token/duration fields and request controls.
