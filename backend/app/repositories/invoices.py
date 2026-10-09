import json
from datetime import datetime, timezone
from decimal import Decimal

from app import database
from app.schemas import InvoiceValidationResponse, ParsedInvoiceResponse


class DuplicateInvoiceError(Exception):
    pass


def _record_from_row(row) -> dict:
    record = dict(row)
    for field in ("subtotal", "tax", "total"):
        record[field] = Decimal(record[field]) if record[field] is not None else None
    record["is_valid"] = bool(record["is_valid"])
    record["errors"] = json.loads(record.pop("errors_json"))
    record["warnings"] = json.loads(record.pop("warnings_json"))
    record["checks"] = json.loads(record.pop("checks_json"))
    return record


def save_upload_metadata(upload_id: str, original_filename: str) -> None:
    database.initialize_database()
    with database.connect() as connection:
        connection.execute(
            "INSERT OR REPLACE INTO uploaded_files (upload_id, original_filename) VALUES (?, ?)",
            (upload_id, original_filename),
        )


def get_upload_metadata(upload_id: str) -> str | None:
    database.initialize_database()
    with database.connect() as connection:
        row = connection.execute(
            "SELECT original_filename FROM uploaded_files WHERE upload_id = ?",
            (upload_id,),
        ).fetchone()
    return row["original_filename"] if row else None


def get_invoice_by_upload_id(upload_id: str) -> dict | None:
    database.initialize_database()
    with database.connect() as connection:
        row = connection.execute(
            "SELECT * FROM invoices WHERE upload_id = ?", (upload_id,)
        ).fetchone()
    return _record_from_row(row) if row else None


def create_invoice(
    invoice: ParsedInvoiceResponse,
    validation: InvoiceValidationResponse,
    original_filename: str,
) -> dict:
    database.initialize_database()
    created_at = datetime.now(timezone.utc).isoformat()
    checks = [check.model_dump() for check in validation.checks]
    values = (
        invoice.upload_id,
        original_filename,
        invoice.invoice_number,
        invoice.invoice_date,
        invoice.vendor_name,
        str(invoice.subtotal) if invoice.subtotal is not None else None,
        str(invoice.tax) if invoice.tax is not None else None,
        str(invoice.total) if invoice.total is not None else None,
        invoice.currency,
        int(validation.is_valid),
        json.dumps(validation.errors),
        json.dumps(validation.warnings),
        json.dumps(checks),
        created_at,
    )

    with database.connect() as connection:
        existing = connection.execute(
            "SELECT id FROM invoices WHERE upload_id = ?", (invoice.upload_id,)
        ).fetchone()
        if existing:
            raise DuplicateInvoiceError("This upload has already been processed.")
        cursor = connection.execute(
            """
            INSERT INTO invoices (
                upload_id, original_filename, invoice_number, invoice_date,
                vendor_name, subtotal, tax, total, currency, is_valid,
                errors_json, warnings_json, checks_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            values,
        )
        invoice_id = cursor.lastrowid
        row = connection.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
    return _record_from_row(row)


def list_invoices() -> list[dict]:
    database.initialize_database()
    with database.connect() as connection:
        rows = connection.execute(
            "SELECT * FROM invoices ORDER BY created_at DESC, id DESC"
        ).fetchall()
    return [_record_from_row(row) for row in rows]


def get_invoice(invoice_id: int) -> dict | None:
    database.initialize_database()
    with database.connect() as connection:
        row = connection.execute(
            "SELECT * FROM invoices WHERE id = ?", (invoice_id,)
        ).fetchone()
    return _record_from_row(row) if row else None


def delete_invoice(invoice_id: int) -> tuple[bool, str | None]:
    database.initialize_database()
    with database.connect() as connection:
        row = connection.execute(
            "SELECT upload_id FROM invoices WHERE id = ?", (invoice_id,)
        ).fetchone()
        if row is None:
            return False, None

        upload_id = row["upload_id"]
        shared_upload = connection.execute(
            "SELECT 1 FROM invoices WHERE upload_id = ? AND id <> ? LIMIT 1",
            (upload_id, invoice_id),
        ).fetchone()
        connection.execute("DELETE FROM invoices WHERE id = ?", (invoice_id,))
        if shared_upload:
            return True, None

        connection.execute(
            "DELETE FROM uploaded_files WHERE upload_id = ?", (upload_id,)
        )
    return True, upload_id
