import streamlit as st
import os
import sys
import cv2
import pytesseract
import pandas as pd
import tempfile

_APP_DIR = os.path.dirname(os.path.abspath(__file__))
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)
sys.path.append(os.path.abspath(os.path.join(_APP_DIR, "..")))

from src.paths import resolve_poppler_bin, resolve_tesseract_cmd
from src.pdf_converter import convert_pdfs_to_images
from src.preprocess import preprocess_image
from src.ocr_engine import run_ocr, get_full_text
from src.extractor import extract_fields
from src.visualize import draw_boxes

poppler_bin_path = resolve_poppler_bin()
tesseract_cmd = resolve_tesseract_cmd()
if tesseract_cmd:
    pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

TABLE_ORDER = [
    ("source_file", "Source"),
    ("from_party", "From"),
    ("to_party", "To"),
    ("invoice_number", "Invoice #"),
    ("order_number", "Order #"),
    ("date", "Date"),
    ("payment_details", "Payment"),
    ("invoice_total", "Value (EUR)"),
]


def _display_row(record: dict) -> dict:
    out = {}
    for key, label in TABLE_ORDER:
        val = record.get(key)
        if key == "invoice_total" and val is not None:
            try:
                out[label] = float(val)
            except (TypeError, ValueError):
                out[label] = None
        else:
            out[label] = val if val not in (None, "") else None
    return out


def _rows_for_export(rows: list[dict]) -> pd.DataFrame:
    cols = [k for k, _ in TABLE_ORDER]
    return pd.DataFrame([{k: r.get(k) for k in cols} for r in rows])


st.set_page_config(page_title="Invoice OCR", layout="wide", initial_sidebar_state="collapsed")
st.title("Invoice OCR")
st.caption("Upload PDF invoices — green boxes show OCR words; the table lists extracted fields.")

if not poppler_bin_path:
    st.warning(
        "Poppler was not found. On Windows, run `python scripts/download_poppler.py` from the repo root, "
        "or set **POPPLER_BIN** to the folder that contains `pdfinfo` / `pdfinfo.exe`."
    )

uploaded_files = st.file_uploader("Upload invoice PDFs", type=["pdf"], accept_multiple_files=True)

if uploaded_files:
    if not poppler_bin_path:
        st.error("Poppler is required. Install it or set **POPPLER_BIN**, then try again.")
        st.stop()

    all_results: list[dict] = []

    with tempfile.TemporaryDirectory() as tmpdir:
        for uploaded_file in uploaded_files:
            pdf_path = os.path.join(tmpdir, uploaded_file.name)
            with open(pdf_path, "wb") as f:
                f.write(uploaded_file.read())

        image_paths = convert_pdfs_to_images(
            pdf_dir=tmpdir, image_dir=tmpdir, dpi=300, poppler_path=poppler_bin_path
        )
        st.success(f"Converted {len(image_paths)} page(s) from {len(uploaded_files)} PDF(s).")

        for image_path in image_paths:
            base = os.path.basename(image_path)
            st.divider()
            st.subheader(base)

            image = cv2.imread(image_path)
            if image is None:
                st.error("Could not load the page image.")
                continue

            preprocessed = preprocess_image(image)
            ocr_result = run_ocr(preprocessed)
            full_text = get_full_text(ocr_result)
            extracted = extract_fields(full_text)
            row = {**extracted, "source_file": base}
            all_results.append(row)

            boxed_img = draw_boxes(cv2.cvtColor(image, cv2.COLOR_BGR2RGB), ocr_result)
            st.image(boxed_img, caption="OCR bounding boxes (green)", width="stretch")

            st.dataframe(
                pd.DataFrame([_display_row(row)]),
                hide_index=True,
                use_container_width=True,
            )

        if all_results:
            st.divider()
            st.subheader("All pages")
            summary = pd.DataFrame([_display_row(r) for r in all_results])
            st.dataframe(summary, hide_index=True, use_container_width=True)

            csv = _rows_for_export(all_results).to_csv(index=False).encode("utf-8")
            st.download_button(
                label="Download CSV",
                data=csv,
                file_name="invoices_extracted.csv",
                mime="text/csv",
            )
