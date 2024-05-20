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
import time
import os

# List of URLs to extract links from
urls = [
    'https://www.elections.tn.gov.in/SSR2024_MR_22012024/ac31.html',
    'https://www.elections.tn.gov.in/SSR2024_MR_22012024/ac184.html',
    'https://www.elections.tn.gov.in/SSR2024_MR_22012024/ac185.html'
]

# Function to extract links from a single page
def extract_links(url):
    driver.get(url)
    time.sleep(5)  # Adjust sleep time if necessary to ensure the page fully loads
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    
    # Extract all links
    links = soup.find_all('a', href=True)
    
    # Debug: print extracted links
    print(f"Extracted links from {url}:")
    for link in links:
        print(link['href'])
    
    return [link['href'] for link in links]

# Set up download directory
download_dir = os.path.join(os.getcwd(), "downloads")
os.makedirs(download_dir, exist_ok=True)

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

# Initialize list for failed links
failed_links = []

# Function to process a single link
def process_link(pdf_link):
    try:
        # Load the PDF link
        driver.get(pdf_link)
        
        # Wait for the CAPTCHA image to load
        captcha_image = wait.until(EC.presence_of_element_located((By.ID, 'Image2')))
        
        # Take a screenshot of the CAPTCHA
        captcha_image.screenshot('captcha.png')
        
        # Open the CAPTCHA image and perform OCR
        captcha = Image.open('captcha.png')
        captcha_text = pytesseract.image_to_string(captcha)
        print("Extracted CAPTCHA text:", captcha_text)

        # Enter the CAPTCHA text into the input box
        captcha_input = driver.find_element(By.ID, 'txt_Vcode')
        captcha_input.send_keys(captcha_text.strip())

        # Click the submit button
        submit_button = driver.find_element(By.ID, 'btn_Login')
        submit_button.click()
        
        # Wait for the PDF to download (adjust wait time as needed)
        time.sleep(10)  # Increase sleep time if necessary to ensure download completes
        
        # Check if the PDF is downloaded
        downloaded_files = os.listdir(download_dir)
        print(f"Downloaded files: {downloaded_files}")
        
        # Verify if the new PDF is in the download directory
        if not downloaded_files:
            raise Exception("PDF download failed")
        
        return True

    except Exception as e:
        print(f"Error processing {pdf_link}: {e}")
        return False

# Extract and process links
for page_url in urls:
    pdf_links = extract_links(page_url)
    
    # Debug: print the number of extracted links
    print(f"Number of links extracted from {page_url}: {len(pdf_links)}")
    
    for pdf_link in pdf_links:
        # Construct the full URL if necessary
        if not pdf_link.startswith('http'):
            pdf_link = f'https://www.elections.tn.gov.in/SSR2024_MR_22012024/{pdf_link}'

        # Retry logic
        success = False
        for attempt in range(3):  # Try 3 times
            success = process_link(pdf_link)
            if success:
                break
            time.sleep(5)  # Wait before retrying
        
        if not success:
            failed_links.append(pdf_link)

# Retry failed links
for pdf_link in failed_links:
    success = False
    for attempt in range(3):  # Try 3 times
        success = process_link(pdf_link)
        if success:
            break
        time.sleep(5)  # Wait before retrying
    
    if not success:
        print(f"Final failure for link: {pdf_link}")

# Close the browser
driver.quit()
