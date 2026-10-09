from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app import database
from app.services import uploads

client = TestClient(app)
PDF_BYTES = b"%PDF-1.7\nunit-test document"
PNG_BYTES = b"\x89PNG\r\n\x1a\nunit-test image"


def use_temporary_upload_directory(monkeypatch, tmp_path: Path) -> Path:
    upload_dir = tmp_path / "user-uploads"
    monkeypatch.setattr(uploads, "UPLOADS_DIR", upload_dir)
    monkeypatch.setattr(database, "DATABASE_PATH", tmp_path / "test.sqlite3")
    return upload_dir


def test_upload_accepts_pdf_and_returns_metadata(monkeypatch, tmp_path: Path) -> None:
    upload_dir = use_temporary_upload_directory(monkeypatch, tmp_path)

    response = client.post(
        "/api/invoices/upload",
        files={"file": ("invoice.pdf", PDF_BYTES, "application/pdf")},
    )

    assert response.status_code == 201
    result = response.json()
    assert result["original_filename"] == "invoice.pdf"
    assert result["content_type"] == "application/pdf"
    assert result["file_size"] == len(PDF_BYTES)
    assert result["status"] == "uploaded"
    assert result["upload_id"]
    assert "path" not in result
    assert list(upload_dir.iterdir())[0].read_bytes() == PDF_BYTES


def test_upload_accepts_png_image(monkeypatch, tmp_path: Path) -> None:
    upload_dir = use_temporary_upload_directory(monkeypatch, tmp_path)

    response = client.post(
        "/api/invoices/upload",
        files={"file": ("scan.PNG", PNG_BYTES, "image/png")},
    )

    assert response.status_code == 201
    assert response.json()["content_type"] == "image/png"
    assert response.json()["file_size"] == len(PNG_BYTES)
    assert len(list(upload_dir.iterdir())) == 1


def test_upload_rejects_unsupported_file_type(monkeypatch, tmp_path: Path) -> None:
    upload_dir = use_temporary_upload_directory(monkeypatch, tmp_path)

    response = client.post(
        "/api/invoices/upload",
        files={"file": ("notes.txt", b"not an invoice", "text/plain")},
    )

    assert response.status_code == 400
    assert list(upload_dir.iterdir()) == [] if upload_dir.exists() else True


def test_upload_rejects_oversized_file_and_cleans_partial_file(
    monkeypatch, tmp_path: Path
) -> None:
    upload_dir = use_temporary_upload_directory(monkeypatch, tmp_path)
    oversized_pdf = b"%PDF-1.7\n" + b"x" * uploads.MAX_UPLOAD_SIZE

    response = client.post(
        "/api/invoices/upload",
        files={"file": ("large.pdf", oversized_pdf, "application/pdf")},
    )

    assert response.status_code == 413
    assert list(upload_dir.iterdir()) == []


def test_generated_filenames_are_safe_unique_and_original_paths_are_stripped(
    monkeypatch, tmp_path: Path
) -> None:
    upload_dir = use_temporary_upload_directory(monkeypatch, tmp_path)
    first = client.post(
        "/api/invoices/upload",
        files={"file": (r"C:\fake\path\..\invoice.pdf", PDF_BYTES, "application/pdf")},
    )
    second = client.post(
        "/api/invoices/upload",
        files={"file": ("invoice.pdf", PDF_BYTES, "application/pdf")},
    )

    assert first.status_code == second.status_code == 201
    assert first.json()["original_filename"] == "invoice.pdf"
    names = [path.name for path in upload_dir.iterdir()]
    assert len(names) == 2
    assert len(set(names)) == 2
    assert all(name.endswith(".pdf") and Path(name).stem.isalnum() for name in names)
