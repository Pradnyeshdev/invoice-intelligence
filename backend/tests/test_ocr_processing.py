from io import BytesIO
from pathlib import Path
from uuid import uuid4

import pymupdf as fitz
from fastapi.testclient import TestClient

from app import database
from app.main import app
from app.services import ocr, uploads

client = TestClient(app)

INVOICE_TEXT = """ACME Office Supplies
Invoice Number: ACME-TEST-OCR-001
Invoice Date: 2025-06-15
Currency: USD
Subtotal: 1000.00
Tax: 180.00
Total: 1180.00"""


def configure_storage(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(uploads, "UPLOADS_DIR", tmp_path / "uploads")
    monkeypatch.setattr(database, "DATABASE_PATH", tmp_path / "invoices.sqlite3")


def make_image_bytes() -> bytes:
    document = fitz.open()
    page = document.new_page(width=700, height=300)
    for index, line in enumerate(INVOICE_TEXT.splitlines()):
        page.insert_text((25, 35 + index * 32), line, fontsize=17)
    image_bytes = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False).tobytes("png")
    document.close()
    return image_bytes


def make_pdf_bytes(text: str | None = None, image_bytes: bytes | None = None) -> bytes:
    document = fitz.open()
    page = document.new_page()
    if text:
        for index, line in enumerate(text.splitlines()):
            page.insert_text((72, 72 + index * 18), line)
    if image_bytes:
        page.insert_image(fitz.Rect(40, 40, 570, 780), stream=image_bytes)
    result = document.tobytes()
    document.close()
    return result


def upload(filename: str, content: bytes, content_type: str) -> str:
    response = client.post(
        "/api/invoices/upload",
        files={"file": (filename, content, content_type)},
    )
    assert response.status_code == 201
    return response.json()["upload_id"]


def test_text_pdf_uses_pymupdf_without_calling_ocr(
    monkeypatch, tmp_path: Path
) -> None:
    configure_storage(monkeypatch, tmp_path)

    def unexpected_ocr(*args, **kwargs):
        raise AssertionError("OCR must not be called for a text PDF")

    monkeypatch.setattr(ocr, "extract_image_text", unexpected_ocr)
    upload_id = upload("text-invoice.pdf", make_pdf_bytes(INVOICE_TEXT), "application/pdf")

    response = client.post(f"/api/invoices/{upload_id}/process")

    assert response.status_code == 201
    assert response.json()["invoice_number"] == "ACME-TEST-OCR-001"
    assert response.json()["is_valid"] is True


def test_scanned_pdf_page_uses_ocr_and_reaches_parser(
    monkeypatch, tmp_path: Path
) -> None:
    configure_storage(monkeypatch, tmp_path)
    calls = []

    def fake_ocr(image_bytes: bytes) -> str:
        calls.append(image_bytes)
        return INVOICE_TEXT

    monkeypatch.setattr(ocr, "extract_image_text", fake_ocr)
    upload_id = upload(
        "scanned-invoice.pdf",
        make_pdf_bytes(image_bytes=make_image_bytes()),
        "application/pdf",
    )

    response = client.post(f"/api/invoices/{upload_id}/process")

    assert response.status_code == 201
    assert calls
    assert response.json()["invoice_number"] == "ACME-TEST-OCR-001"
    assert response.json()["subtotal"] == "1000.00"
    assert response.json()["is_valid"] is True


def test_png_upload_uses_ocr_and_reaches_parser(
    monkeypatch, tmp_path: Path
) -> None:
    configure_storage(monkeypatch, tmp_path)
    calls = []

    def fake_ocr(image_bytes: bytes) -> str:
        calls.append(image_bytes)
        return INVOICE_TEXT

    monkeypatch.setattr(ocr, "extract_image_text", fake_ocr)
    upload_id = upload("scanned-invoice.png", make_image_bytes(), "image/png")

    response = client.post(f"/api/invoices/{upload_id}/process")

    assert response.status_code == 201
    assert calls and calls[0].startswith(b"\x89PNG")
    assert response.json()["invoice_number"] == "ACME-TEST-OCR-001"
    assert response.json()["is_valid"] is True


def test_ocr_failure_returns_safe_error(monkeypatch, tmp_path: Path) -> None:
    configure_storage(monkeypatch, tmp_path)
    monkeypatch.setattr(
        ocr,
        "extract_image_text",
        lambda path: (_ for _ in ()).throw(ocr.OcrError("private OCR details")),
    )
    upload_id = upload("broken-scan.png", make_image_bytes(), "image/png")

    response = client.post(f"/api/invoices/{upload_id}/process")

    assert response.status_code == 422
    assert "could not be read" in response.json()["detail"]
    assert "private OCR details" not in response.text
    assert str(tmp_path) not in response.text
    assert "Traceback" not in response.text


def test_missing_tesseract_returns_safe_setup_error(monkeypatch, tmp_path: Path) -> None:
    configure_storage(monkeypatch, tmp_path)
    monkeypatch.setattr(
        ocr,
        "extract_image_text",
        lambda path: (_ for _ in ()).throw(ocr.OcrUnavailableError()),
    )
    upload_id = upload("needs-ocr.png", make_image_bytes(), "image/png")

    response = client.post(f"/api/invoices/{upload_id}/process")

    assert response.status_code == 503
    assert "Install Tesseract" in response.json()["detail"]
    assert str(tmp_path) not in response.text


def test_tesseract_command_can_be_configured(monkeypatch) -> None:
    monkeypatch.setenv(
        "TESSERACT_CMD", r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    )
    commands = []

    class Result:
        returncode = 0
        stdout = b"recognized invoice text"

    def fake_run(command, **kwargs):
        commands.append(command)
        return Result()

    monkeypatch.setattr(ocr.subprocess, "run", fake_run)

    assert ocr.extract_image_text(b"synthetic image bytes") == "recognized invoice text"
    assert commands[0][0] == r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    assert commands[0][1:] == ["stdin", "stdout", "-l", "eng", "--psm", "6"]
