from pathlib import Path
from uuid import uuid4

import pymupdf as fitz
from fastapi.testclient import TestClient

from app.main import app
from app.services import uploads

client = TestClient(app)


def write_pdf(upload_dir: Path, pages: list[str]) -> str:
    upload_dir.mkdir(parents=True, exist_ok=True)
    upload_id = uuid4().hex
    document = fitz.open()
    for text in pages:
        page = document.new_page()
        page.insert_text((72, 72), text)
    document.save(upload_dir / f"{upload_id}.pdf")
    document.close()
    return upload_id


def test_extracts_text_from_single_page_pdf(monkeypatch, tmp_path: Path) -> None:
    upload_dir = tmp_path / "uploads"
    monkeypatch.setattr(uploads, "UPLOADS_DIR", upload_dir)
    upload_id = write_pdf(upload_dir, ["Single page invoice text"])

    response = client.get(f"/api/invoices/{upload_id}/text")

    assert response.status_code == 200
    result = response.json()
    assert result["upload_id"] == upload_id
    assert result["page_count"] == 1
    assert "Single page invoice text" in result["extracted_text"]


def test_extracts_every_page_and_preserves_page_boundaries(
    monkeypatch, tmp_path: Path
) -> None:
    upload_dir = tmp_path / "uploads"
    monkeypatch.setattr(uploads, "UPLOADS_DIR", upload_dir)
    upload_id = write_pdf(upload_dir, ["First page details", "Second page details"])

    response = client.get(f"/api/invoices/{upload_id}/text")

    assert response.status_code == 200
    result = response.json()
    assert result["page_count"] == 2
    assert "First page details" in result["extracted_text"]
    assert "Second page details" in result["extracted_text"]
    assert "\f" in result["extracted_text"]


def test_unknown_upload_id_returns_404(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(uploads, "UPLOADS_DIR", tmp_path / "uploads")

    response = client.get(f"/api/invoices/{'a' * 32}/text")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_non_pdf_upload_returns_400(monkeypatch, tmp_path: Path) -> None:
    upload_dir = tmp_path / "uploads"
    monkeypatch.setattr(uploads, "UPLOADS_DIR", upload_dir)
    upload_dir.mkdir()
    upload_id = uuid4().hex
    (upload_dir / f"{upload_id}.png").write_bytes(b"\x89PNG\r\n\x1a\n")

    response = client.get(f"/api/invoices/{upload_id}/text")

    assert response.status_code == 400
    assert "PDF" in response.json()["detail"]


def test_corrupted_pdf_returns_safe_error_without_path(
    monkeypatch, tmp_path: Path
) -> None:
    upload_dir = tmp_path / "uploads"
    monkeypatch.setattr(uploads, "UPLOADS_DIR", upload_dir)
    upload_dir.mkdir()
    upload_id = uuid4().hex
    (upload_dir / f"{upload_id}.pdf").write_bytes(b"%PDF-1.7\nnot a valid PDF")

    response = client.get(f"/api/invoices/{upload_id}/text")

    assert response.status_code == 422
    assert "corrupted" in response.json()["detail"].lower()
    assert str(upload_dir) not in response.text
