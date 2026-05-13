import json
import re


def parse_euro_number(euro_str):
    """Convert European-style number like '144.570,81' to float 144570.81"""
    try:
        return float(euro_str.replace(".", "").replace(",", "."))
    except (ValueError, TypeError, AttributeError):
        return None


def _norm_token(w: str) -> str:
    return re.sub(r"^[^\w]+|[^\w]+$", "", w or "").lower()


def _looks_iso_date(s: str) -> bool:
    return bool(re.match(r"^\d{4}-\d{2}-\d{2}", (s or "").strip()))


def _stop_after_to(k: int, norms: list[str], words: list[str]) -> bool:
    """True if position k starts metadata / table (end of TO block)."""
    n = norms[k]
    if n == "dear":
        return True
    if n == "pos":
        return True
    if n == "description":
        return True
    if n == "order" and k + 1 < len(norms) and norms[k + 1] == "number":
        return True
    if n == "date" and k + 1 < len(words) and _looks_iso_date(words[k + 1]):
        return True
    if n == "contact":
        return True
    if n == "payment":
        return True
    if n == "price" and k + 1 < len(norms) and norms[k + 1] == "net":
        return True
    if n.startswith("invoice") and k + 1 < len(norms) and norms[k + 1] == "total":
        return True
    return False


def _extract_date(text):
    pat = re.compile(
        r"\bdate\b[:\s#]*"
        r"((?:\d{4}-\d{2}-\d{2})|(?:\d{1,2}\.\d{1,2}\.\d{4})|(?:\d{1,2}/\d{1,2}/\d{2,4}))",
        re.IGNORECASE,
    )
    m = pat.search(text)
    return m.group(1).strip() if m else None


def _extract_payment_details(text):
    patterns = (
        r"(?i)(payment\s+within\s+\d+\s*days?)",
        r"(?i)payment\s+details[:\s]+(payment\s+within\s+\d+\s*days?)",
        r"(?i)payment\s+details[:\s]+(\d+\s*days?)",
        r"(?i)payment\s+details[:\s]+([\d]{1,2}[./-][\d]{1,2}[./-][\d]{2,4})",
    )
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return None


def _extract_invoice_number(text: str) -> str | None:
    patterns = (
        r"(?i)invoice\s*#\s*(\d{3,})",
        r"(?i)invoice\s+#\s*(\d{3,})",
        r"(?i)invoice[^\d]{0,12}(\d{4,})",
        r"(?i)#\s*(\d{4,})\b",
    )
    for p in patterns:
        m = re.search(p, text)
        if m:
            return m.group(1).strip()
    return None


def _extract_order_number(text: str) -> str | None:
    patterns = (
        r"(?i)order\s+number[:\s#]*(\d+)",
        r"(?i)order\s+no\.?\s*[:\s#]*(\d+)",
    )
    for p in patterns:
        m = re.search(p, text)
        if m:
            return m.group(1).strip()
    return None


def _extract_line_items(text: str) -> list[dict]:
    """
    Heuristic line-item rows inside the table region (between header and Price net).
    """
    flat = re.sub(r"\s+", " ", text)
    start = None
    for m in re.finditer(r"(?i)\bPOS\b\s+\bDESCRIPTION\b", flat):
        start = m.end()
        break
    if start is None:
        m2 = re.search(r"(?i)\bPOS\b\s+(\d)\s", flat)
        if m2:
            start = m2.start()
    if start is None:
        return []
    end_m = re.search(r"(?i)\bPrice\s+net\b", flat[start:])
    segment = flat[start : start + end_m.start()] if end_m else flat[start:]

    pat = re.compile(
        r"(?i)\b(\d{1,3})\s+"
        r"(.+?)\s+"
        r"(\d{1,6})\s+"
        r"Pcs\.?\s+"
        r"([\d\.,]+)\s*€\s+"
        r"([\d\.,]+)\s*€"
    )
    rows = []
    for m in pat.finditer(segment):
        pos, desc, amt, unit_p, line_t = m.groups()
        desc = re.sub(r"\s+", " ", desc).strip()
        if len(desc) < 5:
            continue
        try:
            pi = int(pos)
        except ValueError:
            continue
        if pi < 1 or pi > 200:
            continue
        if re.search(r"(?i)\b(TO|FROM|ORDER\s+NUMBER|DATE|DEAR)\b", desc):
            continue
        rows.append(
            {
                "pos": pos.strip(),
                "description": desc[:500],
                "amount": amt.strip(),
                "unit_price_eur": unit_p.strip(),
                "line_total_eur": line_t.strip(),
            }
        )
    return rows


def _from_to_from_words(words: list[str]) -> tuple[str | None, str | None]:
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
            if _stop_after_to(k, norms, words):
                i_end = k
                break
        from_text = " ".join(words[i_from + 1 : i_to]).strip()
        to_text = " ".join(words[i_to + 1 : i_end]).strip()
        if len(from_text) > 2 and len(to_text) > 2:
            return from_text, to_text
    return None, None


def _extract_from_to_regex(text: str) -> tuple[str | None, str | None]:
    flat = re.sub(r"\s+", " ", text)
    patterns = (
        r"(?i)\bFROM\b\s+(.+?)\s+\bTO\b\s+(.+?)(?=\s+\bORDER\s+NUMBER\b)",
        r"(?i)\bFROM\b\s+(.+?)\s+\bTO\b\s+(.+?)(?=\s+\bDATE\b\s+\d)",
        r"(?i)\bFROM\b\s+(.+?)\s+\bTO\b\s+(.+?)(?=\s+\bDear\b)",
        r"(?i)\bFROM\b\s+(.+?)\s+\bTO\b\s+(.+?)(?=\s+\bPOS\b)",
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

    line_items = _extract_line_items(text)

    results = {
        "from_party": from_party,
        "to_party": to_party,
        "invoice_number": _extract_invoice_number(text),
        "order_number": _extract_order_number(text),
        "date": _extract_date(text),
        "payment_details": _extract_payment_details(text),
        "line_items": line_items,
        "line_items_json": json.dumps(line_items, ensure_ascii=False) if line_items else None,
    }

    total_str = extract_field(text, r"INVOICE\s+TOTAL\s+([\d\.]+,[\d]{2})\s?€?")
    results["invoice_total"] = parse_euro_number(total_str) if total_str else None

    return results


def extract_field(text, pattern):
    match = re.findall(pattern, text, re.IGNORECASE)
    return match[0].strip() if match else None
