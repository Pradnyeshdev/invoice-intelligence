import re
from decimal import Decimal, InvalidOperation

from app.schemas import ParsedInvoiceResponse

AMOUNT_PATTERN = re.compile(
    r"\(?-?\s*(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{1,2})?\)?"
)
DATE_PATTERN = re.compile(
    r"(?:\d{4}[/-]\d{1,2}[/-]\d{1,2}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|"
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|"
    r"Dec(?:ember)?)\.?\s+\d{1,2},?\s+\d{4}|"
    r"\d{1,2}\s+(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|"
    r"Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|"
    r"Nov(?:ember)?|Dec(?:ember)?)\.?\s+\d{4})",
    re.IGNORECASE,
)

CURRENCY_PATTERNS = (
    (re.compile(r"\bINR\b", re.IGNORECASE), "INR"),
    (re.compile(r"\bUSD\b", re.IGNORECASE), "USD"),
    (re.compile(r"\bEUR\b", re.IGNORECASE), "EUR"),
    (re.compile(r"\bGBP\b", re.IGNORECASE), "GBP"),
    (re.compile(r"₹|\bRs\.?\b", re.IGNORECASE), "INR"),
    (re.compile(r"\$"), "USD"),
    (re.compile(r"€"), "EUR"),
    (re.compile(r"£"), "GBP"),
)


def _first_labeled_value(text: str, label_pattern: str) -> str | None:
    pattern = re.compile(
        rf"^\s*(?:{label_pattern})\s*(?::|#|\s+-\s*)?\s*(.*?)\s*$",
        re.IGNORECASE | re.MULTILINE,
    )
    match = pattern.search(text)
    return match.group(1).strip() if match else None


def _parse_invoice_number(text: str) -> str | None:
    value = _first_labeled_value(text, r"Invoice\s*(?:Number|No\.?|#)")
    if not value:
        return None
    match = re.search(r"[A-Za-z0-9][A-Za-z0-9/_-]*", value)
    return match.group(0) if match else None


def _parse_invoice_date(text: str) -> str | None:
    value = _first_labeled_value(text, r"(?:Invoice\s+Date|Date)")
    match = DATE_PATTERN.search(value or "")
    return match.group(0) if match else None


def _parse_vendor_name(text: str) -> str | None:
    # Prefer an explicit supplier/vendor label when one is present.
    labeled = _first_labeled_value(text, r"(?:Vendor\s+Name|Vendor|Supplier|Seller|From)")
    if labeled:
        return labeled or None

    # Otherwise use the first meaningful header line. This is only a heuristic:
    # an address or another header item may be mistaken for the vendor.
    ignored_headers = {"invoice", "tax invoice", "commercial invoice", "bill"}
    for line in text.splitlines():
        candidate = " ".join(line.split()).strip(" :#-")
        if not candidate or candidate.casefold() in ignored_headers:
            continue
        if re.match(r"^(?:invoice\s*(?:number|no\.?|#|date)|date|subtotal|tax|gst|vat|total)\b", candidate, re.I):
            continue
        if re.match(r"^(?:invoice\s*(?:number|no\.?|#)|date|subtotal|tax|gst|vat|total)\s*[:#-]", candidate, re.I):
            continue
        if re.fullmatch(r"[\d\W]+", candidate):
            continue
        return candidate
    return None


def _parse_money(text: str, label_pattern: str) -> Decimal | None:
    value = _first_labeled_value(text, label_pattern)
    if not value:
        return None
    match = AMOUNT_PATTERN.search(value)
    if not match:
        return None
    normalized = match.group(0).replace(",", "").replace(" ", "")
    if normalized.startswith("(") and normalized.endswith(")"):
        normalized = f"-{normalized[1:-1]}"
    try:
        return Decimal(normalized)
    except InvalidOperation:
        return None


def _parse_currency(text: str) -> str | None:
    first_match: tuple[int, str] | None = None
    for pattern, currency in CURRENCY_PATTERNS:
        match = pattern.search(text)
        if match and (first_match is None or match.start() < first_match[0]):
            first_match = (match.start(), currency)
    if first_match:
        return first_match[1]

    # Preserve an explicitly labeled three-letter code so validation can warn
    # when the application does not support that currency yet.
    labeled_code = re.search(r"^\s*Currency\s*:\s*([A-Z]{3})\s*$", text, re.I | re.M)
    return labeled_code.group(1).upper() if labeled_code else None


def parse_invoice_text(upload_id: str, extracted_text: str) -> ParsedInvoiceResponse:
    """Extract common invoice fields from PDF text using deterministic rules."""
    return ParsedInvoiceResponse(
        upload_id=upload_id,
        invoice_number=_parse_invoice_number(extracted_text),
        invoice_date=_parse_invoice_date(extracted_text),
        vendor_name=_parse_vendor_name(extracted_text),
        subtotal=_parse_money(extracted_text, r"Subtotal"),
        tax=_parse_money(extracted_text, r"(?:Tax|GST|VAT)"),
        total=_parse_money(extracted_text, r"(?:Grand\s+Total|Amount\s+Due|Total)"),
        currency=_parse_currency(extracted_text),
    )
