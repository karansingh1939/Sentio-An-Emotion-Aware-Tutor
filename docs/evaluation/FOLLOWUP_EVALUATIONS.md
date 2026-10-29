# Grading and OCR follow-up evaluations

The grading experiment retains all v1 rubrics and adds 14 contrasts: equivalent
wording and numeric forms, incorrect magnitudes and units, contradictions,
incomplete answers, and requests to change the grade. The v2 labels are synthetic
and author-written. They are development data, not an independently labelled test
set. Exact and blank answers are reported separately from model inference.

Completed measurements: [grading comparison](../../reports/GRADING_FOLLOWUP_2026-10-11.md)
and [synthetic OCR evaluation](../../reports/OCR_EVALUATION_2026-10-11.md).

```powershell
uv run python scripts/eval/evaluate_grading.py --repeats 3 --output reports/grading-comparison.json
```

Each request uses empty history, temperature zero, and the existing 512-token
limit. The script alternates baseline/candidate order across repeats, saves each
completed run, and records the model digest, prompts, dataset hash and hardware.
Retain the current production prompt unless repeated measurements improve rubric
pass counts without increasing false positives. Report unsuccessful experiments.
The experiment uses your local Ollama model and can take several minutes.

The OCR evaluator generates labelled English PNG, JPEG, rotated, blurred,
scanned-PDF and mixed-PDF fixtures in a temporary directory. It checks page
numbers, extraction provenance and rejection of an empty image. Native PDF text
is checked separately. It records word and character edit error rates, latency,
fixture hashes, font hash, package versions and engine version.

```powershell
uv run python scripts/eval/evaluate_ocr.py --output reports/ocr-evaluation.json
```

Requires the OCR extra, Tesseract English data and a scalable font. Pass `--font`
if neither Windows Arial nor Linux DejaVu Sans is available. Missing OCR tools
cause an actionable error; recognition is never simulated in published results.
No learner uploads or database are read. Case, punctuation and whitespace are
normalized for scoring; raw recognized text remains in the report. Rates can
exceed 1 when there are many inserted words or characters.

CI runs this evaluator with real Tesseract and uploads its JSON as a 14-day
artifact using [GitHub's artifact action](https://github.com/actions/upload-artifact).
The OCR gate checks extraction structure and expected empty-image rejection;
it does not assert an unsupported real-world accuracy threshold. The small,
clean synthetic corpus does not cover handwriting, diagrams, multilingual
documents or difficult camera photographs. Independent labels and realistic
scans are required before general OCR accuracy claims.
