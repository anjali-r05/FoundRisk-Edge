import os

import fitz
import openpyxl

from app.services import document_parser as parser


def test_parse_pdf_extracts_claims(sample_pdf_path):
    result = parser.parse_pdf(sample_pdf_path)
    assert result.status == "ready"
    assert result.page_count == 3
    assert len(result.claims) > 0
    assert any(c["metric_type"] == "revenue" for c in result.claims)
    assert any(c["metric_type"] == "customer_count" for c in result.claims)
    assert any(c["metric_type"] == "market_size" for c in result.claims)
    assert all(c["source_page"] is not None for c in result.claims)


def test_parse_pdf_empty_pages(tmp_path):
    path = tmp_path / "empty.pdf"
    doc = fitz.open()
    doc.new_page()
    doc.save(str(path))
    doc.close()

    result = parser.parse_pdf(str(path))
    assert result.status == "empty"
    assert "OCR" in result.status_detail or "image" in result.status_detail.lower()


def test_parse_pdf_image_only_detected_honestly(tmp_path):
    # A page with an embedded image and no text should be reported as
    # image-only, never silently "processed" as if text was found.
    path = tmp_path / "scanned.pdf"
    doc = fitz.open()
    page = doc.new_page()
    # draw a filled rectangle to simulate a scanned image region with no text layer
    page.draw_rect(fitz.Rect(50, 50, 400, 600), fill=(0.8, 0.8, 0.8))
    doc.save(str(path))
    doc.close()

    result = parser.parse_pdf(str(path))
    assert result.status == "empty"
    assert "OCR" in result.status_detail


def test_parse_pdf_malformed_file(tmp_path):
    path = tmp_path / "not_a_pdf.pdf"
    path.write_bytes(b"this is not a real pdf file")
    result = parser.parse_pdf(str(path))
    assert result.status == "failed"
    assert result.status_detail


def test_parse_csv_extracts_claims(sample_csv_path):
    result = parser.parse_csv(sample_csv_path)
    assert result.status == "ready"
    assert len(result.claims) > 0
    assert all(c["source_row"] is not None for c in result.claims)
    assert all(c["source_column"] is not None for c in result.claims)


def test_parse_csv_empty(tmp_path):
    path = tmp_path / "empty.csv"
    path.write_text("col_a,col_b\n", encoding="utf-8")
    result = parser.parse_csv(str(path))
    assert result.status == "empty"


def test_parse_csv_malformed(tmp_path):
    # A CSV with a NUL byte trips pandas' C parser
    path = tmp_path / "malformed.csv"
    with open(path, "wb") as f:
        f.write(b"col_a,col_b\n\x001,2\n")
    result = parser.parse_csv(str(path))
    assert result.status in ("failed", "ready")  # pandas may recover; must not raise uncaught


def test_parse_xlsx_extracts_claims_with_real_cell_refs(tmp_path):
    path = tmp_path / "financials.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Financials"
    ws.append(["Revenue FY24", "Revenue FY25"])
    ws.append(["₹2.5 Cr", "₹8 Cr"])
    wb.save(str(path))

    result = parser.parse_xlsx(str(path))
    assert result.status == "ready"
    assert len(result.claims) == 2
    cells = {c["source_cell"] for c in result.claims}
    assert cells == {"A2", "B2"}


def test_parse_xlsx_empty_workbook(tmp_path):
    path = tmp_path / "empty.xlsx"
    wb = openpyxl.Workbook()
    wb.save(str(path))
    result = parser.parse_xlsx(str(path))
    assert result.status == "empty"


def test_parse_xlsx_malformed_file(tmp_path):
    path = tmp_path / "not_real.xlsx"
    path.write_bytes(b"not a real xlsx file")
    result = parser.parse_xlsx(str(path))
    assert result.status == "failed"


def test_parse_document_unsupported_type(tmp_path):
    path = tmp_path / "file.docx"
    path.write_text("irrelevant", encoding="utf-8")
    result = parser.parse_document(str(path), "docx")
    assert result.status == "failed"


def test_parse_scanned_pdf_uses_local_ocr_when_tesseract_is_available(tmp_path):
    import shutil
    import pytest
    from PIL import Image, ImageDraw, ImageFont

    if not shutil.which("tesseract"):
        pytest.skip("Tesseract binary is not installed on this test machine")

    image_path = tmp_path / "scan.png"
    image = Image.new("RGB", (1800, 500), "white")
    draw = ImageDraw.Draw(image)
    draw.text((80, 120), "Revenue: 4.5 Cr in FY2025", fill="black", font=ImageFont.truetype("DejaVuSans.ttf", 72))
    image.save(image_path)

    pdf_path = tmp_path / "scanned_financials.pdf"
    doc = fitz.open()
    page = doc.new_page(width=900, height=250)
    page.insert_image(page.rect, filename=str(image_path))
    doc.save(str(pdf_path))
    doc.close()

    result = parser.parse_pdf(str(pdf_path))
    assert result.status == "ready"
    assert result.ocr_pages == 1
    assert any(claim["metric_type"] == "revenue" for claim in result.claims)
    assert "OCR" in (result.status_detail or "")
