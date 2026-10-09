from decimal import Decimal
from typing import Literal

from pydantic import BaseModel


class InvoiceUploadResponse(BaseModel):
    upload_id: str
    original_filename: str
    content_type: str
    file_size: int
    status: str


class ExtractedDocumentTextResponse(BaseModel):
    upload_id: str
    page_count: int
    extracted_text: str


class ParsedInvoiceResponse(BaseModel):
    upload_id: str
    invoice_number: str | None = None
    invoice_date: str | None = None
    vendor_name: str | None = None
    subtotal: Decimal | None = None
    tax: Decimal | None = None
    total: Decimal | None = None
    currency: str | None = None


class ValidationCheck(BaseModel):
    name: str
    status: Literal["passed", "failed", "warning", "skipped"]
    message: str


class InvoiceValidationResponse(BaseModel):
    upload_id: str
    is_valid: bool
    errors: list[str]
    warnings: list[str]
    checks: list[ValidationCheck]


class InvoiceRecordResponse(BaseModel):
    id: int
    upload_id: str
    original_filename: str
    invoice_number: str | None = None
    invoice_date: str | None = None
    vendor_name: str | None = None
    subtotal: Decimal | None = None
    tax: Decimal | None = None
    total: Decimal | None = None
    currency: str | None = None
    is_valid: bool
    errors: list[str]
    warnings: list[str]
    checks: list[ValidationCheck]
    created_at: str
