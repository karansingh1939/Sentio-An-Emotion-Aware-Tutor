import subprocess

import pytest
from PIL import Image
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from sentio.ingestion import ocr


def pdf_file(path, texts):
    writer = PdfWriter()
    for text in texts:
        page = writer.add_blank_page(612, 792)
        if text:
            font = DictionaryObject(
                {
                    NameObject("/Type"): NameObject("/Font"),
                    NameObject("/Subtype"): NameObject("/Type1"),
                    NameObject("/BaseFont"): NameObject("/Helvetica"),
                }
            )
            page[NameObject("/Resources")] = DictionaryObject(
                {
                    NameObject("/Font"): DictionaryObject(
                        {NameObject("/F1"): writer._add_object(font)}
                    )
                }
            )
            stream = DecodedStreamObject()
            stream.set_data(f"BT /F1 16 Tf 50 700 Td ({text}) Tj ET".encode())
            page[NameObject("/Contents")] = writer._add_object(stream)
    writer.write(path)


def test_native_pdf_does_not_require_ocr(tmp_path, monkeypatch):
    path = tmp_path / "text.pdf"
    pdf_file(path, ["Native text must remain intact."])
    monkeypatch.setattr(ocr, "require_ocr", lambda **kw: pytest.fail("Native text invoked OCR"))
    assert ocr.pdf_pages(path)[0]["text"] == "Native text must remain intact."


def test_scanned_and_mixed_pdf_keep_original_page_citations(tmp_path, monkeypatch):
    pytest.importorskip("pypdfium2")
    path = tmp_path / "mixed.pdf"
    pdf_file(path, ["Native page text retained.", "", ""])
    monkeypatch.setattr(ocr, "require_ocr", lambda **kw: "fake-tesseract")
    monkeypatch.setattr(ocr, "read_image", lambda image: "Extracted scanned page text.")
    pages = ocr.pdf_pages(path)
    assert [p["page_number"] for p in pages] == [1, 2, 3]
    assert [p["extraction_method"] for p in pages] == ["text", "ocr", "ocr"]
    assert pages[0]["text"] == "Native page text retained."


def test_missing_tools_and_encrypted_pdf_are_actionable(tmp_path, monkeypatch):
    monkeypatch.setattr(ocr, "tesseract_path", lambda: None)
    path = tmp_path / "scan.pdf"
    pdf_file(path, [""])
    with pytest.raises(ocr.ExtractionError, match="TESSERACT_CMD"):
        ocr.pdf_pages(path)
    writer = PdfWriter()
    writer.add_blank_page(612, 792)
    writer.encrypt("secret")
    writer.write(path)
    with pytest.raises(ocr.ExtractionError, match="Encrypted"):
        ocr.pdf_pages(path)


def test_ocr_page_limit_applies_only_to_scanned_pages(tmp_path, monkeypatch):
    path = tmp_path / "large.pdf"
    pdf_file(path, [""] * 21)
    with pytest.raises(ocr.ExtractionError, match="20 OCR pages"):
        ocr.pdf_pages(path)
    pdf_file(path, ["A native page requires no OCR."] * 21)
    assert len(ocr.pdf_pages(path)) == 21


def test_rotated_image_chooses_readable_orientation(tmp_path, monkeypatch):
    monkeypatch.setattr(ocr, "require_ocr", lambda **kw: "fake-tesseract")
    calls = []

    def recognize(command, **kwargs):
        with Image.open(command[1]) as image:
            calls.append(image.size)
        confidence = 95 if calls[-1] == (200, 400) else 10
        return subprocess.CompletedProcess(
            command,
            0,
            f"header\n5\t1\t1\t1\t1\t1\t0\t0\t20\t20\t{confidence}\tReadable English words",
            "",
        )

    monkeypatch.setattr(ocr.subprocess, "run", recognize)
    assert ocr.read_image(Image.new("RGB", (400, 200), "white")) == "Readable English words"
    assert (200, 400) in calls


def test_empty_and_oversized_images_are_rejected(monkeypatch):
    monkeypatch.setattr(ocr, "require_ocr", lambda **kw: "fake-tesseract")
    monkeypatch.setattr(
        ocr.subprocess, "run", lambda *a, **kw: subprocess.CompletedProcess(a, 0, "header\n", "")
    )
    with pytest.raises(ocr.ExtractionError, match="No readable English"):
        ocr.read_image(Image.new("RGB", (100, 100), "white"))
    with pytest.raises(ocr.ExtractionError, match="16 million"):
        ocr.read_image(Image.new("RGB", (4001, 4000)))


@pytest.mark.live
@pytest.mark.skipif(not ocr.tesseract_path(), reason="Tesseract executable is not installed")
def test_real_tesseract_reads_generated_english_image(tmp_path):
    from PIL import ImageDraw, ImageFont

    image = Image.new("RGB", (1500, 240), "white")
    fonts = ["C:/Windows/Fonts/arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
    font = next(
        (ImageFont.truetype(f, 42) for f in fonts if __import__("pathlib").Path(f).exists()),
        ImageFont.load_default(size=42),
    )
    ImageDraw.Draw(image).text((30, 70), "Energy is measured in joules.", fill="black", font=font)
    image.save(tmp_path / "scan.png")
    assert "joules" in ocr.image_page(tmp_path / "scan.png")[0]["text"].lower()
