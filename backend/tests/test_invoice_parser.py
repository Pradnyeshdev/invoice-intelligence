from pathlib import Path
from uuid import uuid4

import pymupdf as fitz
from fastapi.testclient import TestClient

from app.main import app
from app.services import uploads

client = TestClient(app)


def save_generated_pdf(upload_dir: Path, text: str) -> str:
    upload_dir.mkdir(parents=True, exist_ok=True)
    upload_id = uuid4().hex
    document = fitz.open()
    page = document.new_page()
    for index, line in enumerate(text.splitlines()):
        page.insert_text((72, 72 + index * 18), line)
    document.save(upload_dir / f"{upload_id}.pdf")
    document.close()
    return upload_id


def test_parses_all_major_invoice_fields(monkeypatch, tmp_path: Path) -> None:
    upload_dir = tmp_path / "uploads"
    monkeypatch.setattr(uploads, "UPLOADS_DIR", upload_dir)
    upload_id = save_generated_pdf(
        upload_dir,
        "ACME Office Supplies\n"
        "Invoice Number: ACME-2026-014\n"
        "Invoice Date: 2026-10-08\n"
        "Subtotal: $1,000.00\n"
        "Tax: $80.00\n"
        "Grand Total: $1,080.00",
    )

    response = client.get(f"/api/invoices/{upload_id}/parsed")

    assert response.status_code == 200
    result = response.json()
    assert result == {
        "upload_id": upload_id,
        "invoice_number": "ACME-2026-014",
        "invoice_date": "2026-10-08",
        "vendor_name": "ACME Office Supplies",
        "subtotal": "1000.00",
        "tax": "80.00",
        "total": "1080.00",
        "currency": "USD",
    }


def test_missing_optional_fields_are_null(monkeypatch, tmp_path: Path) -> None:
    upload_dir = tmp_path / "uploads"
    monkeypatch.setattr(uploads, "UPLOADS_DIR", upload_dir)
    upload_id = save_generated_pdf(upload_dir, "INVOICE")

    response = client.get(f"/api/invoices/{upload_id}/parsed")

    assert response.status_code == 200
    result = response.json()
    assert result["upload_id"] == upload_id
    assert result["invoice_number"] is None
    assert result["invoice_date"] is None
    assert result["vendor_name"] is None
    assert result["subtotal"] is None
    assert result["tax"] is None
    assert result["total"] is None
    assert result["currency"] is None


def test_supports_alternate_labels_and_inr(monkeypatch, tmp_path: Path) -> None:
    upload_dir = tmp_path / "uploads"
    monkeypatch.setattr(uploads, "UPLOADS_DIR", upload_dir)
    upload_id = save_generated_pdf(
        upload_dir,
        "Supplier: Northwind Paper\n"
        "Invoice No: NWP-83\n"
        "Date: 10/09/2026\n"
        "Subtotal: INR 1,000.00\n"
        "GST: INR 180.00\n"
        "Amount Due: INR 1,180.00",
    )

    response = client.get(f"/api/invoices/{upload_id}/parsed")

    assert response.status_code == 200
    result = response.json()
    assert result["invoice_number"] == "NWP-83"
    assert result["invoice_date"] == "10/09/2026"
    assert result["vendor_name"] == "Northwind Paper"
    assert result["subtotal"] == "1000.00"
    assert result["tax"] == "180.00"
    assert result["total"] == "1180.00"
    assert result["currency"] == "INR"


def test_unknown_upload_id_returns_404(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(uploads, "UPLOADS_DIR", tmp_path / "uploads")

    response = client.get(f"/api/invoices/{'b' * 32}/parsed")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_corrupted_pdf_returns_safe_422(monkeypatch, tmp_path: Path) -> None:
    upload_dir = tmp_path / "uploads"
    monkeypatch.setattr(uploads, "UPLOADS_DIR", upload_dir)
    upload_dir.mkdir()
    upload_id = uuid4().hex
    (upload_dir / f"{upload_id}.pdf").write_bytes(b"%PDF-1.7\ninvalid PDF content")

    response = client.get(f"/api/invoices/{upload_id}/parsed")

    assert response.status_code == 422
    assert "could not" in response.json()["detail"].lower() or "corrupted" in response.json()["detail"].lower()
    assert str(upload_dir) not in response.text


def test_non_pdf_upload_returns_400(monkeypatch, tmp_path: Path) -> None:
    upload_dir = tmp_path / "uploads"
    monkeypatch.setattr(uploads, "UPLOADS_DIR", upload_dir)
    upload_dir.mkdir()
    upload_id = uuid4().hex
    (upload_dir / f"{upload_id}.png").write_bytes(b"\x89PNG\r\n\x1a\n")

    response = client.get(f"/api/invoices/{upload_id}/parsed")

    assert response.status_code == 400
    assert "PDF" in response.json()["detail"]
