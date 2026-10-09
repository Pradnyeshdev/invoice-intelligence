import re
from pathlib import Path

import pymupdf as fitz

from app.schemas import ExtractedDocumentTextResponse
from app.services import uploads
from app.services import ocr

UPLOAD_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")


class DocumentExtractionError(Exception):
    def __init__(self, message: str, status_code: int) -> None:
        super().__init__(message)
        self.status_code = status_code


def _find_upload(upload_id: str) -> tuple[Path, str]:
    if not UPLOAD_ID_PATTERN.fullmatch(upload_id):
        raise DocumentExtractionError("Uploaded document was not found.", 404)

    for extension in (".pdf", ".png", ".jpg"):
        candidate = uploads.UPLOADS_DIR / f"{upload_id}{extension}"
        if candidate.is_file():
            return candidate, extension
    raise DocumentExtractionError("Uploaded document was not found.", 404)


def _extract_pdf_pages(path: Path, *, run_ocr: bool = False) -> list[str]:
    try:
        with path.open("rb") as uploaded_file:
            if uploaded_file.read(5) != b"%PDF-":
                raise DocumentExtractionError(
                    "The uploaded PDF is unreadable or corrupted.", 422
                )
        with fitz.open(path) as document:
            page_text = []
            for page in document:
                text = page.get_text()
                if _has_usable_text(text) or not run_ocr:
                    page_text.append(text)
                else:
                    pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                    try:
                        text = ocr.extract_image_text(pixmap.tobytes("png"))
                    except ocr.OcrUnavailableError:
                        raise DocumentExtractionError(
                            "This scanned PDF needs local OCR. Install Tesseract and its English language data.",
                            503,
                        ) from None
                    except ocr.OcrError:
                        raise DocumentExtractionError(
                            "Text could not be read from the scanned PDF page.", 422
                        ) from None
                    page_text.append(text)
            if not page_text:
                raise DocumentExtractionError("The uploaded PDF contains no readable pages.", 422)
    except DocumentExtractionError:
        raise
    except (fitz.FileDataError, fitz.EmptyFileError, OSError, ValueError):
        raise DocumentExtractionError("The uploaded PDF is unreadable or corrupted.", 422) from None
    except Exception:
        # Keep parser details and paths out of the API response.
        raise DocumentExtractionError("The uploaded PDF could not be read.", 422) from None

    return page_text


def _has_usable_text(text: str) -> bool:
    # Very short selectable fragments are common in scanned PDFs and are not
    # enough to reliably parse invoice fields. Keep OCR on a per-page basis.
    return sum(character.isalnum() for character in text) >= 20


def _validate_image_file(path: Path) -> None:
    try:
        with fitz.open(path) as image_document:
            if image_document.page_count != 1:
                raise DocumentExtractionError("The uploaded image is unreadable or corrupted.", 422)
            image_document[0].get_pixmap()
    except DocumentExtractionError:
        raise
    except Exception:
        raise DocumentExtractionError("The uploaded image is unreadable or corrupted.", 422) from None


def extract_document_text(upload_id: str) -> ExtractedDocumentTextResponse:
    path, extension = _find_upload(upload_id)
    if extension == ".pdf":
        page_text = _extract_pdf_pages(path, run_ocr=True)
    else:
        _validate_image_file(path)
        try:
            page_text = [ocr.extract_image_file_text(path)]
        except ocr.OcrUnavailableError:
            raise DocumentExtractionError(
                "Image OCR is unavailable. Install Tesseract and its English language data.", 503
            ) from None
        except ocr.OcrError:
            raise DocumentExtractionError(
                "Text could not be read from the uploaded image.", 422
            ) from None
    return ExtractedDocumentTextResponse(
        upload_id=upload_id,
        page_count=len(page_text),
        extracted_text="\n\f\n".join(page_text),
    )


def extract_pdf_text(upload_id: str) -> ExtractedDocumentTextResponse:
    """Compatibility wrapper for the original PDF-only extraction endpoint."""
    path, extension = _find_upload(upload_id)
    if extension != ".pdf":
        raise DocumentExtractionError(
            "Text extraction is currently supported for PDF files only.", 400
        )
    page_text = _extract_pdf_pages(path, run_ocr=False)
    return ExtractedDocumentTextResponse(
        upload_id=upload_id,
        page_count=len(page_text),
        extracted_text="\n\f\n".join(page_text),
    )
