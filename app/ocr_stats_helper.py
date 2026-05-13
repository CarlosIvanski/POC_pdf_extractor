"""OCR aggregates — lives next to app.py so Streamlit Cloud always ships it with the UI."""


def ocr_stats(ocr_dict: dict) -> dict:
    """Mean confidence (0–100) and non-empty word count from Tesseract output."""
    confidences: list[float] = []
    word_count = 0
    texts = ocr_dict.get("text") or []
    confs = ocr_dict.get("conf") or []
    for i, t in enumerate(texts):
        t = (t or "").strip()
        if not t:
            continue
        word_count += 1
        if i < len(confs):
            try:
                c = int(float(confs[i]))
            except (TypeError, ValueError):
                continue
            if c >= 0:
                confidences.append(float(c))
    mean_c = sum(confidences) / len(confidences) if confidences else None
    return {
        "ocr_mean_confidence": round(mean_c, 1) if mean_c is not None else None,
        "ocr_word_count": word_count,
    }
