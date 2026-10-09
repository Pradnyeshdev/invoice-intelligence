from pathlib import Path
import re
from uuid import uuid4

from fastapi import UploadFile

from app.repositories import invoices as invoice_repository

MAX_UPLOAD_SIZE = 10 * 1024 * 1024
UPLOADS_DIR = Path(__file__).resolve().parents[2] / "uploads"
CHUNK_SIZE = 1024 * 1024
UPLOAD_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")


class UploadError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


def _safe_original_name(filename: str | None) -> str:
    # Strip both POSIX and Windows path components before returning a display name.
    return (filename or "upload").replace("\\", "/").rsplit("/", 1)[-1] or "upload"


def _detect_file_type(prefix: bytes) -> tuple[str, str] | None:
    if prefix.startswith(b"%PDF-"):
        return ".pdf", "application/pdf"
    if prefix.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png", "image/png"
    if prefix.startswith(b"\xff\xd8\xff"):
        return ".jpg", "image/jpeg"
    return None


async def save_invoice_upload(file: UploadFile) -> dict[str, str | int]:
    original_name = _safe_original_name(file.filename)
    extension = Path(original_name).suffix.lower()
    allowed_extensions = {".pdf", ".png", ".jpg", ".jpeg"}
    if extension not in allowed_extensions:
        raise UploadError("Unsupported file type. Upload a PDF, PNG, or JPEG file.")

    first_chunk = await file.read(CHUNK_SIZE)
    detected_type = _detect_file_type(first_chunk)
    if detected_type is None:
        raise UploadError("File contents do not match a supported PDF, PNG, or JPEG format.")
    generated_extension, content_type = detected_type
    matching_extensions = {generated_extension}
    if generated_extension == ".jpg":
        matching_extensions.add(".jpeg")
    if extension not in matching_extensions:
        raise UploadError("File extension does not match its contents.")

    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    upload_id = uuid4().hex
    destination = UPLOADS_DIR / f"{upload_id}{generated_extension}"
    size = 0
    with destination.open("xb") as saved_file:
        try:
            chunk = first_chunk
            while chunk:
                size += len(chunk)
                if size > MAX_UPLOAD_SIZE:
                    raise UploadError("File exceeds the 10 MB maximum size.", status_code=413)
                saved_file.write(chunk)
                chunk = await file.read(CHUNK_SIZE)
        except Exception:
            saved_file.close()
            destination.unlink(missing_ok=True)
            raise

    try:
        invoice_repository.save_upload_metadata(upload_id, original_name)
    except Exception:
        destination.unlink(missing_ok=True)
        raise

    return {
        "upload_id": upload_id,
        "original_filename": original_name,
        "content_type": content_type,
        "file_size": size,
        "status": "uploaded",
    }


def delete_uploaded_file(upload_id: str) -> None:
    """Delete only generated upload names for a validated upload ID."""
    if not UPLOAD_ID_PATTERN.fullmatch(upload_id):
        return
    for extension in (".pdf", ".png", ".jpg"):
        path = UPLOADS_DIR / f"{upload_id}{extension}"
        try:
            path.unlink(missing_ok=True)
        except OSError:
            raise UploadError(
                "The invoice record was deleted, but its uploaded file could not be removed.",
                status_code=503,
            ) from None
