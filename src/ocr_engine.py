import pytesseract
from pytesseract import Output

def run_ocr(img):
    return pytesseract.image_to_data(img, output_type=Output.DICT)

def get_full_text(ocr_dict):
    return " ".join(ocr_dict['text'])
