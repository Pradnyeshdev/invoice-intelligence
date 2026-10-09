"""Optional local OCR adapter backed by the Tesseract command-line tool."""

from pathlib import Path
import os
import subprocess


class OcrUnavailableError(Exception):
    """Raised when the optional Tesseract executable is missing."""


class OcrError(Exception):
    """Raised when Tesseract cannot recognize an image."""


def _executable() -> str:
    """Use configured Tesseract, then the standard Windows path, then PATH."""
    configured = os.environ.get("TESSERACT_CMD", "").strip()
    if configured:
        return configured
    if os.name == "nt":
        windows_install = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
        if windows_install.is_file():
            return str(windows_install)
    return "tesseract"


def extract_image_text(image_bytes: bytes) -> str:
    """Send image bytes to Tesseract over stdin; no document contents are logged."""
    try:
        result = subprocess.run(
            [_executable(), "stdin", "stdout", "-l", "eng", "--psm", "6"],
            input=image_bytes,
            capture_output=True,
            timeout=30,
            check=False,
        )
    except FileNotFoundError:
        raise OcrUnavailableError from None
    except subprocess.TimeoutExpired:
        raise OcrError from None
    except OSError:
        raise OcrUnavailableError from None

    if result.returncode != 0:
        raise OcrError
    text = result.stdout.decode("utf-8", errors="replace")
    if not text.strip():
        raise OcrError
    return text


def extract_image_file_text(path: Path) -> str:
    try:
        image_bytes = path.read_bytes()
    except OSError:
        raise OcrError from None
    return extract_image_text(image_bytes)
