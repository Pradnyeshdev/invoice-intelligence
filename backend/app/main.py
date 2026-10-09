from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi import File, HTTPException, Response, UploadFile

from app import database
from app.repositories import invoices as invoice_repository
from app.repositories.invoices import DuplicateInvoiceError
from app.schemas import (
    ExtractedDocumentTextResponse,
    InvoiceRecordResponse,
    InvoiceValidationResponse,
    InvoiceUploadResponse,
    ParsedInvoiceResponse,
)
from app.services.document_extractor import (
    DocumentExtractionError,
    extract_document_text,
    extract_pdf_text,
)
from app.services.invoice_parser import parse_invoice_text
from app.services.invoice_validator import validate_invoice
from app.services.uploads import UploadError, delete_uploaded_file, save_invoice_upload

app = FastAPI(title="Invoice Intelligence API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health_check() -> dict[str, str]:
    return {"status": "healthy"}


@app.post("/api/invoices/upload", response_model=InvoiceUploadResponse, status_code=201)
async def upload_invoice(file: UploadFile = File(...)) -> InvoiceUploadResponse:
    try:
        return await save_invoice_upload(file)
    except UploadError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except database.DatabaseError as exc:
        raise HTTPException(status_code=503, detail="The local database is unavailable.") from exc
    finally:
        await file.close()


@app.get(
    "/api/invoices/{upload_id}/text",
    response_model=ExtractedDocumentTextResponse,
)
def get_invoice_text(upload_id: str) -> ExtractedDocumentTextResponse:
    try:
        return extract_pdf_text(upload_id)
    except DocumentExtractionError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@app.get(
    "/api/invoices/{upload_id}/parsed",
    response_model=ParsedInvoiceResponse,
)
def get_parsed_invoice(upload_id: str) -> ParsedInvoiceResponse:
    try:
        document = extract_pdf_text(upload_id)
        return parse_invoice_text(upload_id, document.extracted_text)
    except DocumentExtractionError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@app.post(
    "/api/invoices/{upload_id}/validate",
    response_model=InvoiceValidationResponse,
)
def validate_uploaded_invoice(upload_id: str) -> InvoiceValidationResponse:
    try:
        document = extract_pdf_text(upload_id)
        invoice = parse_invoice_text(upload_id, document.extracted_text)
        return validate_invoice(invoice)
    except DocumentExtractionError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@app.post(
    "/api/invoices/{upload_id}/process",
    response_model=InvoiceRecordResponse,
    status_code=201,
)
def process_uploaded_invoice(upload_id: str) -> InvoiceRecordResponse:
    try:
        if invoice_repository.get_invoice_by_upload_id(upload_id):
            raise HTTPException(status_code=409, detail="This upload has already been processed.")

        document = extract_document_text(upload_id)
        invoice = parse_invoice_text(upload_id, document.extracted_text)
        validation = validate_invoice(invoice)
        original_filename = invoice_repository.get_upload_metadata(upload_id)
        if original_filename is None:
            original_filename = f"{upload_id}.pdf"
        return invoice_repository.create_invoice(invoice, validation, original_filename)
    except DocumentExtractionError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except DuplicateInvoiceError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except database.DatabaseError as exc:
        raise HTTPException(status_code=503, detail="The local database is unavailable.") from exc


@app.get("/api/invoices", response_model=list[InvoiceRecordResponse])
def get_invoice_history() -> list[InvoiceRecordResponse]:
    try:
        return invoice_repository.list_invoices()
    except database.DatabaseError as exc:
        raise HTTPException(status_code=503, detail="The local database is unavailable.") from exc


@app.get("/api/invoices/{invoice_id}", response_model=InvoiceRecordResponse)
def get_stored_invoice(invoice_id: int) -> InvoiceRecordResponse:
    try:
        record = invoice_repository.get_invoice(invoice_id)
    except database.DatabaseError as exc:
        raise HTTPException(status_code=503, detail="The local database is unavailable.") from exc
    if record is None:
        raise HTTPException(status_code=404, detail="Invoice record was not found.")
    return record


@app.delete("/api/invoices/{invoice_id}", status_code=204)
def delete_stored_invoice(invoice_id: int) -> Response:
    try:
        deleted, upload_id = invoice_repository.delete_invoice(invoice_id)
    except database.DatabaseError as exc:
        raise HTTPException(status_code=503, detail="The local database is unavailable.") from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="Invoice record was not found.")
    if upload_id:
        try:
            delete_uploaded_file(upload_id)
        except UploadError as exc:
            raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    return Response(status_code=204)
