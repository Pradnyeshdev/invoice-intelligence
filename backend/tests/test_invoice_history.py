from pathlib import Path
from uuid import uuid4

import pymupdf as fitz
from fastapi.testclient import TestClient

from app import database
from app.main import app
from app.repositories import invoices as invoice_repository
from app.services import uploads

client = TestClient(app)


def configure_test_storage(monkeypatch, tmp_path: Path) -> Path:
    upload_dir = tmp_path / "uploads"
    monkeypatch.setattr(uploads, "UPLOADS_DIR", upload_dir)
    monkeypatch.setattr(database, "DATABASE_PATH", tmp_path / "test-invoices.sqlite3")
    return upload_dir


def make_pdf_bytes(lines: list[str]) -> bytes:
    document = fitz.open()
    page = document.new_page()
    for index, line in enumerate(lines):
        page.insert_text((72, 72 + index * 18), line)
    content = document.tobytes()
    document.close()
    return content


def upload_invoice(lines: list[str], filename: str = "portfolio-invoice.pdf") -> dict:
    response = client.post(
        "/api/invoices/upload",
        files={"file": (filename, make_pdf_bytes(lines), "application/pdf")},
    )
    assert response.status_code == 201
    return response.json()


def sample_invoice_lines() -> list[str]:
    return [
        "ACME Office Supplies",
        "Invoice Number: ACME-2025-014",
        "Invoice Date: 2025-05-20",
        "Subtotal: USD 100.00",
        "Tax: USD 8.00",
        "Total: USD 108.00",
    ]


def process_uploaded_invoice(lines: list[str] | None = None) -> tuple[dict, dict]:
    uploaded = upload_invoice(lines or sample_invoice_lines())
    response = client.post(f"/api/invoices/{uploaded['upload_id']}/process")
    assert response.status_code == 201
    return uploaded, response.json()


def test_database_initialization_creates_required_tables(
    monkeypatch, tmp_path: Path
) -> None:
    configure_test_storage(monkeypatch, tmp_path)

    database.initialize_database()
    with database.connect() as connection:
        table_names = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }

    assert {"invoices", "uploaded_files"}.issubset(table_names)


def test_process_valid_invoice_persists_structured_result(
    monkeypatch, tmp_path: Path
) -> None:
    configure_test_storage(monkeypatch, tmp_path)
    uploaded = upload_invoice(sample_invoice_lines(), "acme-original.pdf")

    response = client.post(f"/api/invoices/{uploaded['upload_id']}/process")

    assert response.status_code == 201
    result = response.json()
    assert result["upload_id"] == uploaded["upload_id"]
    assert result["original_filename"] == "acme-original.pdf"
    assert result["invoice_number"] == "ACME-2025-014"
    assert result["subtotal"] == "100.00"
    assert result["tax"] == "8.00"
    assert result["total"] == "108.00"
    assert result["currency"] == "USD"
    assert result["is_valid"] is True
    assert result["errors"] == []
    assert result["id"] > 0


def test_processed_invoice_appears_in_history(monkeypatch, tmp_path: Path) -> None:
    configure_test_storage(monkeypatch, tmp_path)
    uploaded, stored = process_uploaded_invoice()

    response = client.get("/api/invoices")

    assert response.status_code == 200
    history = response.json()
    assert len(history) == 1
    assert history[0]["id"] == stored["id"]
    assert history[0]["upload_id"] == uploaded["upload_id"]


def test_invoice_history_is_newest_first(monkeypatch, tmp_path: Path) -> None:
    configure_test_storage(monkeypatch, tmp_path)
    first_upload, first_record = process_uploaded_invoice()
    second_upload, second_record = process_uploaded_invoice(
        [line.replace("2025-05-20", "2025-05-21") for line in sample_invoice_lines()]
    )

    history = client.get("/api/invoices").json()

    assert first_upload["upload_id"] != second_upload["upload_id"]
    assert [entry["id"] for entry in history] == [second_record["id"], first_record["id"]]


def test_get_individual_stored_invoice(monkeypatch, tmp_path: Path) -> None:
    configure_test_storage(monkeypatch, tmp_path)
    _, stored = process_uploaded_invoice()

    response = client.get(f"/api/invoices/{stored['id']}")

    assert response.status_code == 200
    assert response.json()["id"] == stored["id"]
    assert response.json()["vendor_name"] == "ACME Office Supplies"


def test_delete_invoice_removes_record_metadata_and_uploaded_file(
    monkeypatch, tmp_path: Path
) -> None:
    upload_dir = configure_test_storage(monkeypatch, tmp_path)
    uploaded, stored = process_uploaded_invoice()
    original_path = upload_dir / f"{uploaded['upload_id']}.pdf"
    assert original_path.exists()

    response = client.delete(f"/api/invoices/{stored['id']}")

    assert response.status_code == 204
    assert client.get(f"/api/invoices/{stored['id']}").status_code == 404
    assert client.get("/api/invoices").json() == []
    assert not original_path.exists()
    assert invoice_repository.get_upload_metadata(uploaded["upload_id"]) is None


def test_delete_invoice_never_removes_another_upload_file(
    monkeypatch, tmp_path: Path
) -> None:
    upload_dir = configure_test_storage(monkeypatch, tmp_path)
    first_upload, first_record = process_uploaded_invoice()
    second_upload, second_record = process_uploaded_invoice(
        [line.replace("ACME-2025-014", "ACME-2025-015") for line in sample_invoice_lines()]
    )
    first_path = upload_dir / f"{first_upload['upload_id']}.pdf"
    second_path = upload_dir / f"{second_upload['upload_id']}.pdf"

    response = client.delete(f"/api/invoices/{first_record['id']}")

    assert response.status_code == 204
    assert not first_path.exists()
    assert second_path.exists()
    assert [row["id"] for row in client.get("/api/invoices").json()] == [
        second_record["id"]
    ]


def test_delete_invoice_handles_an_already_missing_upload(
    monkeypatch, tmp_path: Path
) -> None:
    upload_dir = configure_test_storage(monkeypatch, tmp_path)
    uploaded, stored = process_uploaded_invoice()
    (upload_dir / f"{uploaded['upload_id']}.pdf").unlink()

    response = client.delete(f"/api/invoices/{stored['id']}")

    assert response.status_code == 204
    assert client.get("/api/invoices").json() == []


def test_duplicate_processing_returns_conflict(monkeypatch, tmp_path: Path) -> None:
    configure_test_storage(monkeypatch, tmp_path)
    uploaded = upload_invoice(sample_invoice_lines())

    first = client.post(f"/api/invoices/{uploaded['upload_id']}/process")
    duplicate = client.post(f"/api/invoices/{uploaded['upload_id']}/process")

    assert first.status_code == 201
    assert duplicate.status_code == 409
    assert len(client.get("/api/invoices").json()) == 1


def test_process_unknown_upload_returns_404(monkeypatch, tmp_path: Path) -> None:
    configure_test_storage(monkeypatch, tmp_path)

    response = client.post(f"/api/invoices/{'d' * 32}/process")

    assert response.status_code == 404


def test_process_corrupted_pdf_returns_safe_422(monkeypatch, tmp_path: Path) -> None:
    configure_test_storage(monkeypatch, tmp_path)
    uploaded = client.post(
        "/api/invoices/upload",
        files={"file": ("broken.pdf", b"%PDF-1.7\nnot really a PDF", "application/pdf")},
    ).json()

    response = client.post(f"/api/invoices/{uploaded['upload_id']}/process")

    assert response.status_code == 422
    assert str(tmp_path) not in response.text
    assert "Traceback" not in response.text


def test_process_corrupted_image_returns_safe_422(monkeypatch, tmp_path: Path) -> None:
    configure_test_storage(monkeypatch, tmp_path)
    uploaded = client.post(
        "/api/invoices/upload",
        files={"file": ("scan.png", b"\x89PNG\r\n\x1a\n", "image/png")},
    ).json()

    response = client.post(f"/api/invoices/{uploaded['upload_id']}/process")

    assert response.status_code == 422
    assert "corrupted" in response.json()["detail"].lower()
    assert str(tmp_path) not in response.text


def test_database_failure_returns_safe_service_unavailable(monkeypatch, tmp_path: Path) -> None:
    configure_test_storage(monkeypatch, tmp_path)
    database_path_is_directory = tmp_path / "not-a-database-file"
    database_path_is_directory.mkdir()
    monkeypatch.setattr(database, "DATABASE_PATH", database_path_is_directory)

    response = client.get("/api/invoices")

    assert response.status_code == 503
    assert str(tmp_path) not in response.text
    assert "Traceback" not in response.text
