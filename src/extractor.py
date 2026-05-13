import re


def parse_euro_number(euro_str):
    """Convert European-style number like '144.570,81' to float 144570.81"""
    try:
        return float(euro_str.replace(".", "").replace(",", "."))
    except (ValueError, TypeError, AttributeError):
        return None


def _norm_token(w: str) -> str:
    return re.sub(r"^[^\w]+|[^\w]+$", "", w or "").lower()


def _extract_date(text):
    """Value after DATE label (ISO, EU dots, slashes)."""
    pat = re.compile(
        r"\bdate\b[:\s#]*"
        r"((?:\d{4}-\d{2}-\d{2})|(?:\d{1,2}\.\d{1,2}\.\d{4})|(?:\d{1,2}/\d{1,2}/\d{2,4}))",
        re.IGNORECASE,
    )
    m = pat.search(text)
    return m.group(1).strip() if m else None


def _extract_payment_details(text):
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


def _from_to_from_words(words: list[str]) -> tuple[str | None, str | None]:
    """
    Find standalone FROM / TO tokens in reading order; capture text between them.
    Handles layouts where a single-line regex fails (header, two columns, etc.).
    """
    if not words:
        return None, None
    norms = [_norm_token(w) for w in words]
    indices_from = [i for i, n in enumerate(norms) if n == "from"]
    for i_from in indices_from:
        try:
            i_to = next(i for i in range(i_from + 1, len(norms)) if norms[i] == "to")
        except StopIteration:
            continue
        i_end = len(words)
        for k in range(i_to + 1, len(words)):
            n = norms[k]
            if n in ("order", "date", "payment"):
                i_end = k
                break
            if n.startswith("invoice"):
                i_end = k
                break
        from_text = " ".join(words[i_from + 1 : i_to]).strip()
        to_text = " ".join(words[i_to + 1 : i_end]).strip()
        if len(from_text) > 2 and len(to_text) > 2:
            return from_text, to_text
    return None, None


def _extract_from_to_regex(text: str) -> tuple[str | None, str | None]:
    """Fallback when only flat text is available (no OCR dict)."""
    flat = re.sub(r"\s+", " ", text)
    patterns = (
        r"(?i)\bFROM\b\s+(.+?)\s+\bTO\b\s+(.+?)(?=\s+\bORDER\s+NUMBER\b)",
        r"(?i)\bFROM\b\s+(.+?)\s+\bTO\b\s+(.+?)(?=\s+\bDATE\b)",
        r"(?i)\bFROM\b\s+(.+?)\s+\bTO\b\s+(.+?)(?=\s+\bINVOICE\s*#)",
    )
    for p in patterns:
        m = re.search(p, flat)
        if m:
            a, b = m.group(1).strip(), m.group(2).strip()
            if len(a) > 2 and len(b) > 2:
                return a, b
    return None, None


def extract_fields(ocr_dict=None, text: str | None = None):
    """
    Extract invoice fields. Prefer ``ocr_dict`` so FROM/TO can use token order;
    otherwise pass ``text`` (space-separated) for regex-only extraction.
    """
    from src.ocr_engine import iter_words_reading_order

    if ocr_dict is not None:
        words = list(iter_words_reading_order(ocr_dict))
        text = " ".join(words)
    else:
        text = text or ""
        words = text.split()

    from_party, to_party = _from_to_from_words(words)
    if not from_party or not to_party:
        fp2, tp2 = _extract_from_to_regex(text)
        from_party = from_party or fp2
        to_party = to_party or tp2

    results = {
        "from_party": from_party,
        "to_party": to_party,
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
