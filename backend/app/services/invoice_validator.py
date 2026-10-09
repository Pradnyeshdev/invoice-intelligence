from datetime import date, datetime
from decimal import Decimal

from app.schemas import InvoiceValidationResponse, ParsedInvoiceResponse, ValidationCheck

CURRENCY_CODES = {"INR", "USD", "EUR", "GBP"}
AMOUNT_TOLERANCE = Decimal("0.01")
AMOUNT_FIELDS = ("subtotal", "tax", "total")
REQUIRED_FIELDS = (
    ("invoice_number", "Invoice number"),
    ("invoice_date", "Invoice date"),
    ("vendor_name", "Vendor name"),
    ("total", "Total"),
    ("currency", "Currency"),
)
DATE_FORMATS = (
    "%d/%m/%Y",
    "%m/%d/%Y",
    "%d-%m-%Y",
    "%m-%d-%Y",
    "%b %d, %Y",
    "%B %d, %Y",
    "%d %b %Y",
    "%d %B %Y",
)


def _parse_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value)
    except ValueError:
        pass

    for date_format in DATE_FORMATS:
        try:
            return datetime.strptime(value, date_format).date()
        except ValueError:
            continue
    return None


def validate_invoice(invoice: ParsedInvoiceResponse) -> InvoiceValidationResponse:
    """Apply deterministic completeness, date, currency, and amount checks."""
    errors: list[str] = []
    warnings: list[str] = []
    checks: list[ValidationCheck] = []

    for field_name, label in REQUIRED_FIELDS:
        if not getattr(invoice, field_name):
            message = f"{label} is required."
            errors.append(message)
            checks.append(ValidationCheck(name=f"required_{field_name}", status="failed", message=message))
        else:
            checks.append(
                ValidationCheck(
                    name=f"required_{field_name}",
                    status="passed",
                    message=f"{label} is present.",
                )
            )

    parsed_date = _parse_date(invoice.invoice_date) if invoice.invoice_date else None
    if invoice.invoice_date and parsed_date is None:
        message = "Invoice date is not a valid supported date."
        errors.append(message)
        checks.append(ValidationCheck(name="invoice_date_format", status="failed", message=message))
    elif parsed_date is not None:
        checks.append(
            ValidationCheck(
                name="invoice_date_format",
                status="passed",
                message="Invoice date is valid.",
            )
        )
        if parsed_date > date.today():
            message = "Invoice date is in the future; please review it."
            warnings.append(message)
            checks.append(ValidationCheck(name="future_invoice_date", status="warning", message=message))
        else:
            checks.append(
                ValidationCheck(
                    name="future_invoice_date",
                    status="passed",
                    message="Invoice date is not in the future.",
                )
            )
    else:
        checks.append(
            ValidationCheck(
                name="invoice_date_format",
                status="skipped",
                message="Date format check skipped because no invoice date was provided.",
            )
        )

    for field_name in AMOUNT_FIELDS:
        amount = getattr(invoice, field_name)
        if amount is None:
            checks.append(
                ValidationCheck(
                    name=f"non_negative_{field_name}",
                    status="skipped",
                    message=f"{field_name.capitalize()} check skipped because the amount is missing.",
                )
            )
        elif amount < 0:
            message = f"{field_name.capitalize()} must not be negative."
            errors.append(message)
            checks.append(
                ValidationCheck(name=f"non_negative_{field_name}", status="failed", message=message)
            )
        else:
            checks.append(
                ValidationCheck(
                    name=f"non_negative_{field_name}",
                    status="passed",
                    message=f"{field_name.capitalize()} is not negative.",
                )
            )

    if invoice.subtotal is not None and invoice.tax is not None and invoice.total is not None:
        difference = abs(invoice.subtotal + invoice.tax - invoice.total)
        if difference <= AMOUNT_TOLERANCE:
            checks.append(
                ValidationCheck(
                    name="subtotal_plus_tax_equals_total",
                    status="passed",
                    message="Subtotal plus tax matches total within 0.01 rounding tolerance.",
                )
            )
        else:
            message = "Subtotal plus tax does not equal total."
            errors.append(message)
            checks.append(
                ValidationCheck(
                    name="subtotal_plus_tax_equals_total",
                    status="failed",
                    message=message,
                )
            )
    else:
        checks.append(
            ValidationCheck(
                name="subtotal_plus_tax_equals_total",
                status="skipped",
                message="Financial consistency check skipped because subtotal, tax, or total is missing.",
            )
        )

    if invoice.currency and invoice.currency.upper() in CURRENCY_CODES:
        checks.append(
            ValidationCheck(
                name="supported_currency",
                status="passed",
                message=f"Currency {invoice.currency.upper()} is supported.",
            )
        )
    else:
        message = "Currency is missing or unsupported; review the currency code."
        warnings.append(message)
        checks.append(ValidationCheck(name="supported_currency", status="warning", message=message))

    return InvoiceValidationResponse(
        upload_id=invoice.upload_id,
        is_valid=not errors,
        errors=errors,
        warnings=warnings,
        checks=checks,
    )
