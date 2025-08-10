import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.firefox.service import Service
import platform
import sys

if platform.system() == "Windows":
    GECKODRIVER_PATH = r"C:\\Coding\\Github\\WebScrapingDiscordBot\\WebScraper\\bin\\geckodriver\\geckodriver.exe"
else:
    GECKODRIVER_PATH = "/usr/bin/geckodriver"

def check_js_required(url, selector):
    # Try without JS
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "lxml")
            el = soup.select_one(selector)
            if el and el.get_text(strip=True):
                print(f"Selector '{selector}' found price WITHOUT JS: '{el.get_text(strip=True)}'")
                return False
    except Exception as e:
        print(f"Error fetching without JS: {e}")
    # Try with JS
    try:
        options = webdriver.FirefoxOptions()
        options.add_argument('--headless')
        service = Service(GECKODRIVER_PATH)
        driver = webdriver.Firefox(service=service, options=options)
        driver.get(url)
        html = driver.page_source
        driver.quit()
        soup = BeautifulSoup(html, "lxml")
        el = soup.select_one(selector)
        if el and el.get_text(strip=True):
            print(f"Selector '{selector}' found price WITH JS: '{el.get_text(strip=True)}'")
            return True
        else:
            print(f"Selector '{selector}' did not find price even with JS.")
            return None
    except Exception as e:
        print(f"Error fetching with JS: {e}")
        return None

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python check_js_required.py <url> <css_selector>")
        sys.exit(1)
    url = sys.argv[1]
    selector = sys.argv[2]
    js_needed = check_js_required(url, selector)
    if js_needed is True:
        print("JavaScript is required for this selector.")
    elif js_needed is False:
        print("JavaScript is NOT required for this selector.")
    else:
        print("Could not determine if JavaScript is required.")
