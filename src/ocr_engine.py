import pytesseract
from pytesseract import Output


def run_ocr(img):
    return pytesseract.image_to_data(img, output_type=Output.DICT)


def iter_words_reading_order(ocr_dict):
    """
    Words in Tesseract reading order (block → paragraph → line → word index → x).
    Works better than raw dict key order for multi-block invoices (FROM / TO columns).
    """
    n = len(ocr_dict.get("text") or [])
    rows = []
    for i in range(n):
        t = (ocr_dict["text"][i] or "").strip()
        if not t:
            continue
        try:
            rows.append(
                (
                    int(ocr_dict["block_num"][i]),
                    int(ocr_dict["par_num"][i]),
                    int(ocr_dict["line_num"][i]),
                    int(ocr_dict["word_num"][i]),
                    int(ocr_dict["left"][i]),
                    int(ocr_dict["top"][i]),
                    t,
                )
            )
        except (KeyError, IndexError, ValueError, TypeError):
            continue
    rows.sort(key=lambda x: x[:-1])
    for r in rows:
        yield r[-1]


def get_full_text(ocr_dict):
    return " ".join(iter_words_reading_order(ocr_dict))
