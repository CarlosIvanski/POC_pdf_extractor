import streamlit as st
import os
import sys
import cv2
import pytesseract
import pandas as pd
import tempfile

# Add the parent directory of 'app' to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.pdf_converter import convert_pdfs_to_images
from src.preprocess import preprocess_image
from src.ocr_engine import run_ocr, get_full_text
from src.extractor import extract_fields
from src.visualize import draw_boxes

poppler_bin_path = os.path.join(os.getcwd(), "poppler-24.08.0", "Library","bin")
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

st.set_page_config(page_title="Invoice OCR App", layout="centered")
st.title("Invoice OCR - PDF to Structured Data")

uploaded_files = st.file_uploader("Upload Invoice PDFs", type=["pdf"], accept_multiple_files=True)

if uploaded_files:
    all_results = []

    with tempfile.TemporaryDirectory() as tmpdir:
        # Save all uploaded PDFs
        for uploaded_file in uploaded_files:
            pdf_path = os.path.join(tmpdir, uploaded_file.name)
            with open(pdf_path, "wb") as f:
                f.write(uploaded_file.read())

        # Convert all PDFs in tmpdir to images
        image_paths = convert_pdfs_to_images(pdf_dir=tmpdir, image_dir=tmpdir, dpi=300, poppler_path=poppler_bin_path)
        st.success(f"Converted {len(image_paths)} pages from {len(uploaded_files)} PDFs.")

        # Process each image
        for image_path in image_paths:
            st.subheader(f" {os.path.basename(image_path)}")
            image = cv2.imread(image_path)
            if image is None:
                st.error("Failed to load image.")
                continue

            preprocessed = preprocess_image(image)
            ocr_result = run_ocr(preprocessed)
            full_text = get_full_text(ocr_result)
            extracted = extract_fields(full_text)

            # Manual Editing form
            st.write("### Extracted Fields (edit if needed):")
            edited_fields = {}
            for idx, (key, value) in enumerate(extracted.items()):
                unique_key = f"{os.path.basename(image_path)}_{key}_{idx}"
                edited_value = st.text_input(f"{key}", value, key=unique_key)
                edited_fields[key] = edited_value

            all_results.append(edited_fields)

            # Visualize OCR bounding boxes
            boxed_img = draw_boxes(cv2.cvtColor(image, cv2.COLOR_BGR2RGB), ocr_result)
            st.image(boxed_img, caption="OCR Bounding Boxes",  use_container_width=True)

        # Show combined results as a DataFrame
        if all_results:
            df = pd.DataFrame(all_results)
            st.write("### Combined Extracted Data")
            st.dataframe(df)

            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="Download All Data as CSV",
                data=csv,
                file_name="all_invoices_data.csv",
                mime="text/csv"
            )
