"""Synthetic OCR evaluation through the production extraction path."""

import hashlib
import io
import json
import platform
import re
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont
from pypdf import PdfReader, PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from sentio.ingestion import ocr

TEXT = (
    "Energy is measured in joules.\nA base case stops repeated calls.\nHeat flows from hot to cold."
)
NATIVE_TEXT = "Native text retains its original page citation."
CASES = [
    {"id": "png", "format": "png"},
    {"id": "jpeg", "format": "jpeg"},
    {"id": "rotated_90", "format": "png", "angle": 90},
    {"id": "rotated_180", "format": "png", "angle": 180},
    {"id": "rotated_270", "format": "png", "angle": 270},
    {"id": "blurred", "format": "png", "blur_radius": 1},
    {"id": "scanned_pdf", "format": "pdf"},
    {"id": "mixed_pdf", "format": "pdf", "native_first": True},
    {"id": "blank", "format": "png", "blank": True},
]


def distance(reference, hypothesis):
    """Levenshtein edit count with memory proportional to hypothesis length."""
    previous = list(range(len(hypothesis) + 1))
    for i, expected in enumerate(reference, 1):
        current = [i]
        for j, actual in enumerate(hypothesis, 1):
            current.append(
                min(current[-1] + 1, previous[j] + 1, previous[j - 1] + (expected != actual))
            )
        previous = current
    return previous[-1]


def normalize(text):
    return " ".join(re.findall(r"\w+", text.casefold()))


def error_rates(reference, hypothesis):
    reference, hypothesis = normalize(reference), normalize(hypothesis)
    if not reference:
        raise ValueError("OCR metrics require a nonempty reference")
    return {
        "word_error_rate": distance(reference.split(), hypothesis.split()) / len(reference.split()),
        "character_error_rate": distance(reference, hypothesis) / len(reference),
    }


def choose_font(font_path=None):
    candidates = (
        [font_path]
        if font_path
        else [
            Path("C:/Windows/Fonts/arial.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        ]
    )
    for path in candidates:
        if path and Path(path).is_file():
            return Path(path)
    raise ValueError("Install a scalable font or pass --font with a .ttf path")


def native_page(writer):
    page = writer.add_blank_page(612, 792)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})}
    )
    stream = DecodedStreamObject()
    stream.set_data(f"BT /F1 16 Tf 40 700 Td ({NATIVE_TEXT}) Tj ET".encode())
    page[NameObject("/Contents")] = writer._add_object(stream)


def make_fixture(root, case, font_path):
    image = Image.new("RGB", (1600, 400), "white")
    if not case.get("blank"):
        ImageDraw.Draw(image).multiline_text(
            (40, 60), TEXT, fill="black", font=ImageFont.truetype(str(font_path), 44), spacing=20
        )
    if case.get("angle"):
        image = image.rotate(case["angle"], expand=True)
    if case.get("blur_radius"):
        image = image.filter(ImageFilter.GaussianBlur(case["blur_radius"]))
    path = root / f"{case['id']}.{case['format']}"
    if case["format"] == "pdf":
        scan = io.BytesIO()
        image.save(scan, format="PDF", resolution=150)
        writer = PdfWriter()
        if case.get("native_first"):
            native_page(writer)
        writer.add_page(PdfReader(io.BytesIO(scan.getvalue())).pages[0])
        writer.write(path)
    else:
        image.save(path, quality=85)
    image.close()
    return path


def evaluate(font_path=None):
    executable = ocr.require_ocr(pdf=True)
    font = choose_font(font_path)
    engine = subprocess.run(
        [executable, "--version"], capture_output=True, text=True, check=True, timeout=10
    ).stdout.splitlines()[0]
    manifest = {"version": "1.0", "text": TEXT, "native_text": NATIVE_TEXT, "cases": CASES}
    result = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dataset": manifest,
        "dataset_sha256": hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest(),
        "provenance": "Author-generated labelled English scans. No learner data. Not real-world or independently reviewed OCR accuracy.",
        "hardware": {"platform": platform.platform(), "cpu": platform.processor()},
        "configuration": {
            "engine": engine,
            "language": "eng",
            "psm": 6,
            "pdf_dpi": 150,
            "font": str(font),
            "font_sha256": hashlib.sha256(font.read_bytes()).hexdigest(),
            "pillow": version("pillow"),
            "pypdfium2": version("pypdfium2"),
            "normalization": "casefold, punctuation removed, whitespace collapsed",
        },
        "cases": [],
    }
    with tempfile.TemporaryDirectory(prefix="sentio-ocr-eval-") as directory:
        for case in CASES:
            path = make_fixture(Path(directory), case, font)
            row = {
                "id": case["id"],
                "fixture_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
            start = time.perf_counter()
            try:
                pages = ocr.pdf_pages(path) if case["format"] == "pdf" else ocr.image_page(path)
                if case.get("blank"):
                    row.update(structure_pass=False, error="Blank image was accepted")
                else:
                    references = [NATIVE_TEXT, TEXT] if case.get("native_first") else [TEXT]
                    methods = ["text", "ocr"] if case.get("native_first") else ["ocr"]
                    row["structure_pass"] = (
                        len(pages) == len(references)
                        and [p["page_number"] for p in pages] == list(range(1, len(references) + 1))
                        and [p["extraction_method"] for p in pages] == methods
                        and (not case.get("native_first") or pages[0]["text"] == NATIVE_TEXT)
                    )
                    row["pages"] = [
                        dict(page, reference=reference, **error_rates(reference, page["text"]))
                        for page, reference in zip(pages, references)
                    ]
            except ocr.ExtractionError as exc:
                row.update(
                    error=str(exc),
                    structure_pass=bool(
                        case.get("blank") and "No readable English text" in str(exc)
                    ),
                )
            row["latency_ms"] = (time.perf_counter() - start) * 1000
            result["cases"].append(row)
    pages = [
        page
        for case in result["cases"]
        for page in case.get("pages", [])
        if page["extraction_method"] == "ocr"
    ]
    result["summary"] = {
        "structure_passed": sum(case["structure_pass"] for case in result["cases"]),
        "total_cases": len(CASES),
        "ocr_pages_measured": len(pages),
        "mean_word_error_rate": sum(p["word_error_rate"] for p in pages) / len(pages)
        if pages
        else None,
        "mean_character_error_rate": sum(p["character_error_rate"] for p in pages) / len(pages)
        if pages
        else None,
    }
    return result
