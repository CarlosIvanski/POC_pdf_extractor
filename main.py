import os
import sys
import cv2
import pytesseract
import argparse
import logging
import pandas as pd
import matplotlib.pyplot as plt

from src.paths import project_root, resolve_poppler_bin, resolve_tesseract_cmd
from src.pdf_converter import convert_pdfs_to_images
from src.preprocess import preprocess_image
from src.ocr_engine import run_ocr, get_full_text
from src.extractor import extract_fields
from src.visualize import draw_boxes


# --- Set up logging ---
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# --- CLI Args ---
parser = argparse.ArgumentParser(description="Invoice OCR pipeline")
parser.add_argument("--headless", action="store_true", help="Run without showing plots")
args = parser.parse_args()

# --- Paths (repo root, not cwd — reliable with Streamlit / IDEs) ---
root = project_root()
pdf_dir = os.path.join(root, "data", "pdf")
image_dir = os.path.join(root, "data", "raw")
visual_dir = os.path.join(root, "data", "visuals")
output_dir = os.path.join(root, "data", "processed")

poppler_bin_path = resolve_poppler_bin()
if not poppler_bin_path:
    logging.error(
        "Poppler not found (bin folder with pdfinfo). Download Poppler for Windows "
        "(e.g. https://github.com/oschwartz10612/poppler-windows/releases), extract it, "
        "and set POPPLER_BIN to the absolute path of the bin folder "
        "(e.g. C:\\\\poppler\\\\Library\\\\bin)."
    )
    sys.exit(1)

tesseract_cmd = resolve_tesseract_cmd()
if not tesseract_cmd:
    logging.error(
        "Tesseract not found. Install Tesseract or set TESSERACT_CMD to the full path "
        "to tesseract.exe."
    )
    sys.exit(1)
pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

os.makedirs(image_dir, exist_ok=True)
os.makedirs(output_dir, exist_ok=True)
os.makedirs(visual_dir, exist_ok=True)

# --- Step 1: Convert all PDFs to images ---
logging.info("Converting PDFs to images...")
convert_pdfs_to_images(pdf_dir=pdf_dir, image_dir=image_dir, dpi=300, poppler_path=poppler_bin_path)

# --- Step 2: Process images ---
summary = []

for filename in os.listdir(image_dir):
    if not filename.lower().endswith((".jpg", ".jpeg", ".png")):
        continue

    img_path = os.path.join(image_dir, filename)
    logging.info(f"Processing: {filename}")

    img = cv2.imread(img_path)
    if img is None:
        logging.warning(f"Failed to load image: {filename}")
        continue

    # Preprocess + OCR
    preprocessed = preprocess_image(img)
    ocr_result = run_ocr(preprocessed)
    fields = extract_fields(get_full_text(ocr_result))
    fields["source_file"] = filename
    fields.pop("line_items", None)
    summary.append(fields)

    # Draw and save visualization
    boxed_img = draw_boxes(cv2.cvtColor(img, cv2.COLOR_BGR2RGB), ocr_result)
    visual_path = os.path.join(visual_dir, f"{os.path.splitext(filename)[0]}_boxed.jpg")
    plt.imsave(visual_path, boxed_img)
    
    # Show plot only if not headless
    if not args.headless:
        plt.imshow(boxed_img)
        plt.axis('off')
        plt.title(f"OCR: {filename}")
        plt.show()

# --- Step 3: Save output ---
df = pd.DataFrame(summary)
csv_path = os.path.join(output_dir, "invoice_summary.csv")
df.to_csv(csv_path, index=False)
logging.info(f"✅ Done. Output saved to: {csv_path}")
