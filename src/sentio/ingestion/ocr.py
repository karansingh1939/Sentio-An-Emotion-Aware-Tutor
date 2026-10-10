"""Optional, bounded local OCR. PDFium calls are serialized (not thread safe)."""

import importlib.util
import os
import shutil
import subprocess
import tempfile
import threading
from contextlib import closing
from pathlib import Path

from PIL import Image, ImageOps

MAX_OCR_PAGES = 20
MAX_PIXELS = 16_000_000
PDFIUM_LOCK = threading.Lock()


class ExtractionError(ValueError):
    """An actionable document extraction failure."""


def tesseract_path():
    configured = os.getenv("TESSERACT_CMD")
    candidates = [
        configured,
        shutil.which("tesseract"),
        str(Path(os.getenv("ProgramFiles", "C:/Program Files")) / "Tesseract-OCR/tesseract.exe"),
    ]
    return next((str(p) for p in candidates if p and Path(p).is_file()), None)


def require_ocr(pdf=False):
    executable = tesseract_path()
    if not executable:
        raise ExtractionError(
            "OCR requires Tesseract with English language data. Install Tesseract and set TESSERACT_CMD if it is not on PATH."
        )
    if pdf and importlib.util.find_spec("pypdfium2") is None:
        raise ExtractionError("Scanned PDFs require the OCR extra. Run: uv sync --extra ocr")
    return executable


def read_image(image):
    executable = require_ocr()
    if image.width * image.height > MAX_PIXELS:
        raise ExtractionError(
            "OCR images must contain at most 16 million pixels. Resize the image."
        )
    image = ImageOps.exif_transpose(image).convert("RGB")
    best_text, best_score = "", -1
    with tempfile.TemporaryDirectory(prefix="sentio-ocr-") as directory:
        path = Path(directory) / "page.png"
        for angle in (0, 90, 180, 270):
            image.rotate(angle, expand=True).save(path)
            try:
                result = subprocess.run(
                    [executable, str(path), "stdout", "-l", "eng", "--psm", "6", "tsv"],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=30,
                    check=True,
                )
            except subprocess.TimeoutExpired as exc:
                raise ExtractionError(
                    "OCR exceeded the 30 second page-orientation timeout. Try a smaller or clearer image."
                ) from exc
            except subprocess.CalledProcessError as exc:
                raise ExtractionError(
                    "Tesseract failed. Check that English (eng) language data is installed."
                ) from exc
            words, confidences = [], []
            for line in result.stdout.splitlines()[1:]:
                fields = line.split("\t", 11)
                if len(fields) == 12 and fields[11].strip():
                    words.append(fields[11].strip())
                    confidences.append(float(fields[10]))
            score = sum(confidences) / len(confidences) if confidences else -1
            if score > best_score:
                best_text, best_score = " ".join(words), score
            if angle == 0 and score >= 85:
                break
    if len(best_text.strip()) < 10 or best_score < 25:
        raise ExtractionError(
            "No readable English text found. Upload a clearer scan or a text document."
        )
    return best_text


def image_page(filepath):
    try:
        with Image.open(filepath) as image:
            text = read_image(image)
    except (OSError, Image.DecompressionBombError) as exc:
        raise ExtractionError(
            "Image is unreadable or too large. Upload a valid PNG or JPEG."
        ) from exc
    return [{"page_number": 1, "text": text, "extraction_method": "ocr"}]


def pdf_pages(filepath):
    from pypdf import PdfReader

    try:
        reader = PdfReader(filepath)
        if reader.is_encrypted:
            raise ExtractionError("Encrypted PDFs are not supported. Upload an unencrypted copy.")
        pages = [
            {"page_number": i + 1, "text": page.extract_text() or "", "extraction_method": "text"}
            for i, page in enumerate(reader.pages)
        ]
    except ExtractionError:
        raise
    except Exception as exc:
        raise ExtractionError(
            "PDF is unreadable. Export a valid, unencrypted PDF and retry."
        ) from exc
    scanned = [page for page in pages if len(page["text"].strip()) < 10]
    if len(scanned) > MAX_OCR_PAGES:
        raise ExtractionError(
            "Document exceeds the maximum of 20 OCR pages. Split the scanned document."
        )
    if scanned:
        require_ocr(pdf=True)
        import pypdfium2 as pdfium

        with PDFIUM_LOCK, pdfium.PdfDocument(str(filepath)) as document:
            for entry in scanned:
                with closing(document[entry["page_number"] - 1]) as page:
                    width, height = page.get_size()
                    scale = min(150 / 72, (MAX_PIXELS / max(1, width * height)) ** 0.5 * 0.99)
                    with closing(page.render(scale=scale)) as bitmap:
                        image = bitmap.to_pil().copy()
                try:
                    entry["text"] = read_image(image)
                    entry["extraction_method"] = "ocr"
                finally:
                    image.close()
    if not pages:
        raise ExtractionError("PDF contains no pages.")
    return pages
