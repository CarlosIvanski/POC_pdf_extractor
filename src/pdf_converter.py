import os
from pdf2image import convert_from_path

def convert_pdfs_to_images(pdf_dir, image_dir, dpi=300, poppler_path=None):
    os.makedirs(image_dir, exist_ok=True)
    pdf_files = [f for f in os.listdir(pdf_dir) if f.lower().endswith(".pdf")]

    all_image_paths = []

    for pdf_file in pdf_files:
        pdf_path = os.path.join(pdf_dir, pdf_file)
        images = convert_from_path(pdf_path, dpi=dpi, poppler_path=poppler_path)

        base_name = os.path.splitext(pdf_file)[0]
        for i, img in enumerate(images):
            output_filename = f"{base_name}_page{i+1}.jpg"
            output_path = os.path.join(image_dir, output_filename)
            img.save(output_path, "JPEG")
            all_image_paths.append(output_path)

    return all_image_paths