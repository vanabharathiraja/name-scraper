import pytesseract
from PIL import Image
from pdf2image import convert_from_path
import os
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s:%(message)s', handlers=[
    logging.FileHandler("pdf_search.log"),
    logging.StreamHandler()
])

# Set up Tesseract
pytesseract.pytesseract.tesseract_cmd = r'/usr/bin/tesseract'  # Adjust this path as needed
os.environ["TESSDATA_PREFIX"] = "/usr/share/tesseract-ocr/4.00/tessdata/"

# Define directories
download_dir = os.path.join(os.getcwd(), "downloads")
abs_directory = os.path.abspath(download_dir)
temp_dir = os.path.join(os.getcwd(), "temp")
os.makedirs(temp_dir, exist_ok=True)
search_results_dir = os.path.join(os.getcwd(), "results")
os.makedirs(search_results_dir, exist_ok=True)

# Search terms
search_terms = ["அன்னபூரணி", "அனுஷ்யா"]

# Function to search for a name in an image
def search_name_in_image(image, search_name):
    text = pytesseract.image_to_string(image, lang='tam')  # Using Tamil language
    return search_name in text, text

# Function to process a single PDF file
def process_pdf(pdf_path):
    try:
        logging.info(f"Starting conversion for {pdf_path}")
        pages = convert_from_path(pdf_path, dpi=300)  # Ensure DPI is set to 300
        pdf_name = os.path.basename(pdf_path).replace('.pdf', '')
        
        for i, page in enumerate(pages):
            image_path = os.path.join(temp_dir, f"{pdf_name}_page_{i + 1}.png")
            page.save(image_path, 'PNG')
            image = Image.open(image_path)

            for term in search_terms:
                found, extracted_text = search_name_in_image(image, term)
                if found:
                    logging.info(f"Term '{term}' found in {pdf_path} on page {i + 1}")
                    result_file_path = os.path.join(search_results_dir, f"{pdf_name}_{term}_page_{i + 1}_text.txt")
                    with open(result_file_path, "w", encoding="utf-8") as text_file:
                        text_file.write(extracted_text)
            
            logging.info(f"Completed processing page {i + 1} of {pdf_path}")

        logging.info(f"Conversion completed for {pdf_path}, processed all pages")
    except Exception as e:
        logging.error(f"Error processing {pdf_path}: {e}")

# Main function to control the execution
def main():
    pdf_files = [os.path.join(abs_directory, f) for f in os.listdir(download_dir) if f.lower().endswith('.pdf')]
    
    with ThreadPoolExecutor(max_workers=2) as executor:  # Reduced number of threads
        futures = [executor.submit(process_pdf, pdf_file) for pdf_file in pdf_files]
        for future in as_completed(futures):
            # This will raise any exceptions caught by the futures
            future.result()

    logging.info("Finished processing all files.")

if __name__ == "__main__":
    main()
