import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from PIL import Image
import pytesseract
from pdf2image import convert_from_path
import fitz  # PyMuPDF
import time
import os
import concurrent.futures
import logging
import uuid  # For generating unique filenames

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s:%(message)s', handlers=[
    logging.FileHandler("pdf_downloader.log"),
    logging.StreamHandler()
])

# Set up Tesseract
pytesseract.pytesseract.tesseract_cmd = r'/usr/bin/tesseract'  # Adjust this if tesseract is not in this path

# Ensure Tesseract can find the language data files
os.environ["TESSDATA_PREFIX"] = "/usr/share/tesseract-ocr/4.00/tessdata/"

# Directories
download_dir = os.path.join(os.getcwd(), "downloads")
os.makedirs(download_dir, exist_ok=True)
image_dir = os.path.join(os.getcwd(), "pdf_images")
os.makedirs(image_dir, exist_ok=True)
captcha_dir = os.path.join(os.getcwd(), "captchas")
os.makedirs(captcha_dir, exist_ok=True)
search_results_dir = os.path.join(os.getcwd(), "search_results")
os.makedirs(search_results_dir, exist_ok=True)

# URLs to extract links from
urls = [
    'https://www.elections.tn.gov.in/SSR2024_MR_22012024/ac31.html',
    'https://www.elections.tn.gov.in/SSR2024_MR_22012024/ac184.html',
    'https://www.elections.tn.gov.in/SSR2024_MR_22012024/ac185.html'
]

# Search terms
search_terms = ["அன்னபூரணி", "அனுஷ்யா"]

# Function to extract links from a single page
def extract_links(url):
    driver.get(url)
    time.sleep(5)  # Adjust sleep time if necessary to ensure the page fully loads
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    
    # Extract all links
    links = soup.find_all('a', href=True)
    
    return [link['href'] for link in links]

# Set up Selenium WebDriver with download preferences
options = webdriver.ChromeOptions()
options.add_argument('--headless')  # Run headless Chrome
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')

prefs = {
    "download.default_directory": download_dir,
    "plugins.always_open_pdf_externally": True,  # Disable Chrome PDF viewer to force download
}
options.add_experimental_option("prefs", prefs)

driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=options)
wait = WebDriverWait(driver, 10)

# Function to download PDFs and handle CAPTCHA
def download_pdf(pdf_link):
    max_retries = 3  # Number of retries for empty or incorrect CAPTCHA text
    try:
        for attempt in range(max_retries):
            try:
                # Load the PDF link
                driver.get(pdf_link)
                
                # Wait for the CAPTCHA image to load
                captcha_image = wait.until(EC.presence_of_element_located((By.ID, 'Image2')))
                
                # Generate a unique filename for the CAPTCHA image
                captcha_filename = os.path.join(captcha_dir, f"captcha_{uuid.uuid4().hex}.png")
                
                # Take a screenshot of the CAPTCHA
                captcha_image.screenshot(captcha_filename)
                
                # Open the CAPTCHA image and perform OCR
                captcha = Image.open(captcha_filename)
                captcha_text = pytesseract.image_to_string(captcha, lang='tam').strip()
                logging.info(f"Extracted CAPTCHA text: '{captcha_text}'")

                if captcha_text:  # If the CAPTCHA text is not empty, proceed
                    # Enter the CAPTCHA text into the input box
                    captcha_input = driver.find_element(By.ID, 'txt_Vcode')
                    captcha_input.send_keys(captcha_text)

                    # Click the submit button
                    submit_button = driver.find_element(By.ID, 'btn_Login')
                    submit_button.click()
                    
                    # Wait for the PDF to download (adjust wait time as needed)
                    time.sleep(10)  # Increase sleep time if necessary to ensure download completes
                    
                    # Check if the PDF is downloaded
                    downloaded_files = os.listdir(download_dir)
                    if not downloaded_files:
                        raise Exception("PDF download failed")
                    
                    logging.info(f"Downloaded files: {downloaded_files}")
                    
                    # Clean up the CAPTCHA file
                    os.remove(captcha_filename)
                    
                    return pdf_link, True

                else:
                    logging.warning(f"Empty CAPTCHA text on attempt {attempt + 1}. Retrying...")

            except Exception as e:
                logging.warning(f"Retry {attempt + 1}/{max_retries} for {pdf_link} failed with error: {e}")

        logging.error(f"Failed to extract CAPTCHA text after {max_retries} attempts")
        return pdf_link, False

    except Exception as e:
        logging.error(f"Error processing {pdf_link}: {e}")
        return pdf_link, False

# Function to search for a name in an image
def search_name_in_image(image, search_name):
    text = pytesseract.image_to_string(image, lang='tam')  # Use 'tam' for Tamil language
    return search_name in text, text

# Function to process PDF and search for terms
def process_pdf(pdf_path, search_terms):
    try:
        pages = convert_from_path(pdf_path, 300)
        pdf_name = os.path.basename(pdf_path).replace('.pdf', '')
        
        for i, page in enumerate(pages):
            image_path = os.path.join(image_dir, f"{pdf_name}_page_{i + 1}.png")
            page.save(image_path, 'PNG')

            # Search for the terms in the current page image
            image = Image.open(image_path)
            for term in search_terms:
                found, extracted_text = search_name_in_image(image, term)
                if found:
                    logging.info(f"Term '{term}' found in {pdf_path} on page {i + 1}")
                    
                    # Save extracted text and cropped image
                    with open(f"{search_results_dir}/{pdf_name}_{term}_page_{i + 1}_text.txt", "w", encoding="utf-8") as text_file:
                        text_file.write(extracted_text)
                    
                    boxes = pytesseract.image_to_boxes(image, lang='tam')
                    for box in boxes.splitlines():
                        b = box.split(' ')
                        if b[0] == term:
                            x, y, w, h = int(b[1]), int(b[2]), int(b[3]), int(b[4])
                            cropped_image = image.crop((x, image.height - y, w, image.height - h))
                            cropped_image.save(f"{search_results_dir}/{pdf_name}_{term}_section_page_{i + 1}.png")
                            logging.info(f"Saved cropped image for '{term}' from {pdf_path} on page {i + 1}")

    except Exception as e:
        logging.error(f"Error processing {pdf_path}: {e}")

# Extract and process links
pdf_links = []
for page_url in urls:
    links = extract_links(page_url)
    logging.info(f"Number of links extracted from {page_url}: {len(links)}")
    
    for link in links:
        if not link.startswith('http'):
            link = f'https://www.elections.tn.gov.in/SSR2024_MR_22012024/{link}'
        pdf_links.append(link)

# Download PDFs with parallel processing
with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
    future_to_pdf = {executor.submit(download_pdf, link): link for link in pdf_links}
    for future in concurrent.futures.as_completed(future_to_pdf):
        pdf_link = future_to_pdf[future]
        try:
            pdf_link, success = future.result()
            if success:
                logging.info(f"Successfully downloaded PDF from {pdf_link}")
            else:
                logging.error(f"Failed to download PDF from {pdf_link}")
        except Exception as e:
            logging.error(f"Exception occurred while downloading PDF from {pdf_link}: {e}")

# Search downloaded PDFs with parallel processing
downloaded_pdfs = [os.path.join(download_dir, f) for f in os.listdir(download_dir) if f.endswith('.pdf')]
with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
    future_to_search = {executor.submit(process_pdf, pdf, search_terms): pdf for pdf in downloaded_pdfs}
    for future in concurrent.futures.as_completed(future_to_search):
        pdf_path = future_to_search[future]
        try:
            future.result()
            logging.info(f"Successfully processed PDF: {pdf_path}")
        except Exception as e:
            logging.error(f"Exception occurred while processing PDF: {pdf_path}: {e}")

# Close the browser
driver.quit()
