import re


def parse_euro_number(euro_str):
    """Convert European-style number like '144.570,81' to float 144570.81"""
    try:
        return float(euro_str.replace(".", "").replace(",", "."))
    except (ValueError, TypeError, AttributeError):
        return None


def _extract_date(text):
    """Match value after DATE label (ISO, EU dots, slashes — OCR is one long string)."""
    pat = re.compile(
        r"\bdate\b[:\s#]*"
        r"((?:\d{4}-\d{2}-\d{2})|(?:\d{1,2}\.\d{1,2}\.\d{4})|(?:\d{1,2}/\d{1,2}/\d{2,4}))",
        re.IGNORECASE,
    )
    m = pat.search(text)
    return m.group(1).strip() if m else None


def _extract_payment_details(text):
    """
    Text after PAYMENT DETAILS — often '90 days', 'Payment within 90 days', or a due date.
    (Old regex only matched DD.MM.YYYY, which misses typical payment terms.)
    """
    patterns = (
        r"\bpayment\s+details\b[:\s]+(payment\s+within\s+\d+\s*days?)",
        r"\bpayment\s+details\b[:\s]+(\d+\s*days?)",
        r"\bpayment\s+details\b[:\s]+([\d]{1,2}[./-][\d]{1,2}[./-][\d]{2,4})",
    )
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return None


def extract_fields(text):
    results = {
        "invoice_number": extract_field(text, r"Invoice\s*#?:?\s*(\d{3,})"),
        "order_number": extract_field(text, r"ORDER\s*NUMBER\s*[:\s#]*(\d+)"),
        "date": _extract_date(text),
        "payment_details": _extract_payment_details(text),
    }

    total_str = extract_field(text, r"INVOICE\s+TOTAL\s+([\d\.]+,[\d]{2})\s?€?")
    results["invoice_total"] = parse_euro_number(total_str) if total_str else None

    return results


def extract_field(text, pattern):
    match = re.findall(pattern, text, re.IGNORECASE)
    return match[0].strip() if match else None
