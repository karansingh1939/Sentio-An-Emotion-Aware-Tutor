# Optional local OCR decision — 2026-10-11

The existing pypdf parser preserves native text but cannot recover words from
scanned page images. Pillow is already installed, so image decoding needs no new
dependency. The optional `ocr` extra adds pypdfium2 for PDF page rendering;
Tesseract is a separate local executable, called with argument lists and no shell.
No paid API, training, or learner data transfer is involved.

Tesseract uses Apache-2.0. pypdfium2 uses Apache-2.0/BSD-3-Clause and bundles
PDFium with its third-party license notices. See the projects' published
[Tesseract license](https://github.com/tesseract-ocr/tesseract/blob/main/LICENSE)
and [pypdfium2 licensing](https://github.com/pypdfium2-team/pypdfium2#licensing).
Distribution must retain applicable notices; the project's MIT license does not
replace those dependency licenses.

PDF rendering starts at 150 DPI and scales down to a maximum of 16 million
pixels, approximately 48 MiB for one RGB image before additional copies.
Images also have a 16 million pixel limit. These are bounds, not measured peak
memory guarantees. Only one page is rendered at a time. CPU recognition may try
four rotations with a 30 second timeout each; at most 20 OCR pages are accepted.
The upload limit remains 20 MiB. The upload UI allows a longer request deadline
because document extraction can involve multiple page-orientation operations.

PDFium is not thread safe; all document open/render/close work is protected by a
process-wide lock, following its [official API guidance](https://pypdfium2.readthedocs.io/en/stable/python_api.html).
This favors correctness over simultaneous scanned-document throughput.
Tesseract TSV output provides text and confidence for selecting orientations,
using its [documented command-line interface](https://tesseract-ocr.github.io/tessdoc/Command-Line-Usage.html).
Confidence is used only for extraction heuristics, not an OCR accuracy claim.

Inputs remain untrusted: encrypted PDFs are rejected, rendering/image sizes and
OCR page counts are bounded, subprocesses have deadlines, temporary images are
deleted, and failed extraction preserves previous learner documents. Native
text shorter than ten characters is treated as a scan candidate. OCR layout and
language accuracy remain unverified without labelled samples.

Validation: native PDF, mixed/scanned page rendering, rotated recognition
selection, empty inputs, limits, missing tools, encrypted files, and persisted
page provenance have regression tests. A real Tesseract smoke test is included
and runs in OCR-enabled CI. Locally the installer was canceled, so that smoke
test is skipped; no successful local OCR engine run is claimed.
