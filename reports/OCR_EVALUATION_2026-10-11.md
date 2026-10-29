# Measured synthetic OCR evaluation — 2026-10-11

Problem: model/tool availability and mocked extraction tests alone do not show
whether rotated scans, images and mixed PDFs retain readable text and citations.

Experiment: generate English text with known labels in a temporary directory,
then invoke the real production PNG/JPEG/PDF extraction path. Nine cases cover
PNG, JPEG, 90/180/270-degree rotations, mild Gaussian blur, a scanned PDF, a mixed
native/scanned PDF, and blank-image rejection. Eight cases yield an OCR page;
the mixed PDF also contains a native text page. No learner data is used.

Execution: GitHub Actions Ubuntu Linux x86_64 runner, Tesseract 5.3.4 English,
page segmentation mode 6, 150-DPI PDF rendering, Pillow 12.3.0, PDFium binding
5.14.0 and DejaVu Sans font at 44 pixels. Exact dataset, font and fixture hashes,
raw recognized text and timings are saved in
[the measured JSON report](ocr-evaluation-2026-10-11.json). The results came from
[this successful CI run](https://github.com/karansingh-1939/Sentio-An-Emotion-Aware-Tutor/actions/runs/38084720600).

| Check | Observed result |
|---|---|
| Extraction structure and expected blank rejection | 9/9 passed |
| OCR pages measured | 8 |
| Mean normalized word error rate | 0 |
| Mean normalized character error rate | 0 |
| Native mixed-PDF text | Preserved exactly |
| Mixed-PDF citations/methods | Page 1: text; page 2: OCR |
| Upright/image/PDF cases | Approximately 370–393 ms each |
| Rotated cases | Approximately 1.87–1.88 seconds each |

Scoring casefolds text, removes punctuation and collapses whitespace. Native
text is excluded from the OCR error-rate mean. Blank rejection is excluded from
text accuracy and latency ranges above. Rotated cases are slower because the
production extractor tries multiple orientations. This is a single hosted run;
timings are not a local CPU SLA or a repeated performance estimate.

Decision: retain the existing extraction implementation; the benchmark verified
its tested paths without requiring a code change. Keep page citations and
text/OCR provenance. CI now saves each new measurement as a 14-day artifact.
Local Windows still lacks Tesseract, so its live smoke test remains skipped.

Limitations: these are clean generated labels, three short repeated sentences,
one font, one language, mild blur and one engine configuration. Zero error here
does not demonstrate general OCR accuracy. Handwriting, tables, formulas,
low contrast, real camera photos and varied layouts remain unevaluated. Font
and platform differences can change results; PDFs can include generated metadata
that changes their byte hash. Obtain independently reviewed realistic scan labels
before publishing broader accuracy claims.

Reproduce with installed Tesseract English data and the OCR extra:

```powershell
uv run python scripts/eval/evaluate_ocr.py --output reports/ocr-evaluation.json
```
