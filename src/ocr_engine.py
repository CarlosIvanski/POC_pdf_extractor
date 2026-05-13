import pytesseract
from pytesseract import Output

def run_ocr(img):
    return pytesseract.image_to_data(img, output_type=Output.DICT)

def get_full_text(ocr_dict):
    return " ".join(ocr_dict['text'])


def ocr_stats(ocr_dict):
    """Mean confidence (0–100) and non-empty word count from Tesseract output."""
    confidences = []
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
                confidences.append(c)
    mean_c = sum(confidences) / len(confidences) if confidences else None
    return {
        "ocr_mean_confidence": round(mean_c, 1) if mean_c is not None else None,
        "ocr_word_count": word_count,
    }
