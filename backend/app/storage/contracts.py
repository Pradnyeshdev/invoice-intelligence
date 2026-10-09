"""Small interfaces for the persistence operations used by the application."""

from pathlib import Path
from typing import AsyncIterator, Protocol, runtime_checkable

from app.schemas import InvoiceValidationResponse, ParsedInvoiceResponse


@runtime_checkable
class InvoiceMetadataStore(Protocol):
    """Persistence operations required for upload metadata and invoice records."""

    def save_upload_metadata(self, upload_id: str, original_filename: str) -> None: ...

    def get_upload_metadata(self, upload_id: str) -> str | None: ...

    def get_invoice_by_upload_id(self, upload_id: str) -> dict | None: ...

    def create_invoice(
        self,
        invoice: ParsedInvoiceResponse,
        validation: InvoiceValidationResponse,
        original_filename: str,
    ) -> dict: ...

    def list_invoices(self) -> list[dict]: ...

    def get_invoice(self, invoice_id: int) -> dict | None: ...

    def delete_invoice(self, invoice_id: int) -> tuple[bool, str | None]: ...


@runtime_checkable
class UploadedDocumentStore(Protocol):
    """Operations required to save, locate, and remove uploaded documents."""

    async def save_upload(
        self, upload_id: str, extension: str, chunks: AsyncIterator[bytes]
    ) -> int: ...

    def find_upload(self, upload_id: str) -> tuple[Path, str] | None: ...

    def delete_upload(self, upload_id: str) -> None: ...
