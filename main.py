import os
import cv2
import pytesseract
import argparse
import logging
import pandas as pd
import matplotlib.pyplot as plt

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

# --- Paths ---
pdf_dir = "data/pdf"
image_dir = "data/raw"
visual_dir = "data/visuals"
output_dir = "data/processed"
poppler_bin_path = os.path.join(os.getcwd(), "poppler-24.08.0", "Library","bin")
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

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
    full_text = get_full_text(ocr_result)

    # Extract fields
    fields = extract_fields(full_text)
    fields["source_file"] = filename
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
