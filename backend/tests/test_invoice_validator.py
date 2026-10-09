from pathlib import Path
from uuid import uuid4

import pymupdf as fitz
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import uploads

client = TestClient(app)


def save_generated_pdf(upload_dir: Path, lines: list[str]) -> str:
    upload_dir.mkdir(parents=True, exist_ok=True)
    upload_id = uuid4().hex
    document = fitz.open()
    page = document.new_page()
    for index, line in enumerate(lines):
        page.insert_text((72, 72 + index * 18), line)
    document.save(upload_dir / f"{upload_id}.pdf")
    document.close()
    return upload_id


def valid_invoice_lines() -> list[str]:
    return [
        "ACME Office Supplies",
        "Invoice Number: ACME-2025-014",
        "Invoice Date: 2025-05-20",
        "Subtotal: USD 100.00",
        "Tax: USD 8.00",
        "Total: USD 108.00",
    ]


def test_completely_valid_invoice_passes(monkeypatch, tmp_path: Path) -> None:
    upload_dir = tmp_path / "uploads"
    monkeypatch.setattr(uploads, "UPLOADS_DIR", upload_dir)
    upload_id = save_generated_pdf(upload_dir, valid_invoice_lines())

    response = client.post(f"/api/invoices/{upload_id}/validate")

    assert response.status_code == 200
    result = response.json()
    assert result["upload_id"] == upload_id
    assert result["is_valid"] is True
    assert result["errors"] == []
    assert result["warnings"] == []
    checks = {check["name"]: check["status"] for check in result["checks"]}
    assert checks["subtotal_plus_tax_equals_total"] == "passed"
    assert checks["supported_currency"] == "passed"


def test_subtotal_plus_tax_equals_total_with_rounding_tolerance(
    monkeypatch, tmp_path: Path
) -> None:
    upload_dir = tmp_path / "uploads"
    monkeypatch.setattr(uploads, "UPLOADS_DIR", upload_dir)
    lines = valid_invoice_lines()
    lines[-1] = "Total: USD 108.01"
    upload_id = save_generated_pdf(upload_dir, lines)

    response = client.post(f"/api/invoices/{upload_id}/validate")

    assert response.status_code == 200
    assert response.json()["is_valid"] is True


def test_subtotal_plus_tax_mismatch_is_an_error(monkeypatch, tmp_path: Path) -> None:
    upload_dir = tmp_path / "uploads"
    monkeypatch.setattr(uploads, "UPLOADS_DIR", upload_dir)
    lines = valid_invoice_lines()
    lines[-1] = "Total: USD 110.00"
    upload_id = save_generated_pdf(upload_dir, lines)

    response = client.post(f"/api/invoices/{upload_id}/validate")

    result = response.json()
    assert result["is_valid"] is False
    assert "Subtotal plus tax does not equal total." in result["errors"]


def test_missing_required_field_is_an_error(monkeypatch, tmp_path: Path) -> None:
    upload_dir = tmp_path / "uploads"
    monkeypatch.setattr(uploads, "UPLOADS_DIR", upload_dir)
    lines = valid_invoice_lines()
    lines.remove("Invoice Number: ACME-2025-014")
    upload_id = save_generated_pdf(upload_dir, lines)

    result = client.post(f"/api/invoices/{upload_id}/validate").json()

    assert result["is_valid"] is False
    assert "Invoice number is required." in result["errors"]


@pytest.mark.parametrize(
    ("amount_line_index", "replacement"),
    [
        (3, "Subtotal: USD -100.00"),
        (4, "Tax: USD -8.00"),
        (5, "Total: USD -108.00"),
    ],
)
def test_negative_financial_amount_is_an_error(
    monkeypatch,
    tmp_path: Path,
    amount_line_index: int,
    replacement: str,
) -> None:
    upload_dir = tmp_path / "uploads"
    monkeypatch.setattr(uploads, "UPLOADS_DIR", upload_dir)
    lines = valid_invoice_lines()
    lines[amount_line_index] = replacement
    upload_id = save_generated_pdf(upload_dir, lines)

    result = client.post(f"/api/invoices/{upload_id}/validate").json()

    assert result["is_valid"] is False
    assert any("must not be negative" in error for error in result["errors"])


def test_future_invoice_date_is_a_warning_not_an_error(
    monkeypatch, tmp_path: Path
) -> None:
    upload_dir = tmp_path / "uploads"
    monkeypatch.setattr(uploads, "UPLOADS_DIR", upload_dir)
    lines = valid_invoice_lines()
    lines[2] = "Invoice Date: 2099-05-20"
    upload_id = save_generated_pdf(upload_dir, lines)

    result = client.post(f"/api/invoices/{upload_id}/validate").json()

    assert result["is_valid"] is True
    assert any("in the future" in warning for warning in result["warnings"])
    checks = {check["name"]: check["status"] for check in result["checks"]}
    assert checks["future_invoice_date"] == "warning"


def test_unsupported_currency_produces_a_warning(monkeypatch, tmp_path: Path) -> None:
    upload_dir = tmp_path / "uploads"
    monkeypatch.setattr(uploads, "UPLOADS_DIR", upload_dir)
    lines = [line.replace("USD", "CAD") for line in valid_invoice_lines()]
    lines.append("Currency: CAD")
    upload_id = save_generated_pdf(upload_dir, lines)

    result = client.post(f"/api/invoices/{upload_id}/validate").json()

    assert result["is_valid"] is True
    assert result["errors"] == []
    assert any("missing or unsupported" in warning for warning in result["warnings"])
    checks = {check["name"]: check["status"] for check in result["checks"]}
    assert checks["supported_currency"] == "warning"


def test_unknown_upload_id_returns_404(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(uploads, "UPLOADS_DIR", tmp_path / "uploads")

    response = client.post(f"/api/invoices/{'c' * 32}/validate")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_corrupted_pdf_returns_safe_422(monkeypatch, tmp_path: Path) -> None:
    upload_dir = tmp_path / "uploads"
    monkeypatch.setattr(uploads, "UPLOADS_DIR", upload_dir)
    upload_dir.mkdir()
    upload_id = uuid4().hex
    (upload_dir / f"{upload_id}.pdf").write_bytes(b"%PDF-1.7\nnot a PDF")

    response = client.post(f"/api/invoices/{upload_id}/validate")

    assert response.status_code == 422
    assert str(upload_dir) not in response.text
    assert "Traceback" not in response.text


def test_non_pdf_upload_returns_400(monkeypatch, tmp_path: Path) -> None:
    upload_dir = tmp_path / "uploads"
    monkeypatch.setattr(uploads, "UPLOADS_DIR", upload_dir)
    upload_dir.mkdir()
    upload_id = uuid4().hex
    (upload_dir / f"{upload_id}.png").write_bytes(b"\x89PNG\r\n\x1a\n")

    response = client.post(f"/api/invoices/{upload_id}/validate")

    assert response.status_code == 400
    assert "PDF" in response.json()["detail"]
