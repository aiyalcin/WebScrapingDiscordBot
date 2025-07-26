from bs4 import BeautifulSoup
import requests
import re
from selenium import webdriver
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.common.by import By
import JsonHandler
import PriceTracker
import LogHandler as lh

GECKODRIVER_PATH = r"C:\Coding\Github\WebScrapingDiscordBot\WebScraper\bin\geckodriver-v0.36.0-win64\geckodriver.exe"

def extractPrice(object, DEBUG):
    lh.log(f"Now scraping ID: {object['id']}", "log")
    try:
        url = object['url']
        selector = object['selector']
        use_js = object.get('js', False)  # Default to False if not set

        if use_js:
            options = webdriver.FirefoxOptions()
            options.add_argument('--headless')
            service = Service(GECKODRIVER_PATH)
            driver = webdriver.Firefox(service=service, options=options)
            driver.get(url)
            price_element = driver.find_element(By.CSS_SELECTOR, selector)
            price_text = price_element.text
            driver.quit()
        else:
            html_text = requests.get(url).text
            soup = BeautifulSoup(html_text, "lxml")
            price_element = soup.select_one(selector)
            if not price_element:
                lh.log(f"Could not find price element for {object['name']}", "error")
                return None
            price_text = price_element.get_text(strip=True)

        match = re.search(r'\d+(?:[.,]\d{2})?', price_text)
        if match:
            clean_price = match.group(0)
        else:
            lh.log(f"Could not extract price from text: '{price_text}'", "error")
            return None

        if not DEBUG:
            JsonHandler.update_site_price(object['id'], clean_price)
        else:
            lh.log("Skipping write DEBUG is enabled", "warn")

        return clean_price
    except Exception as e:
        lh.log(f"Error extracting price for {object.get('name', 'unknown')}: {e}", "error")
        return None


def getAllPrices(DEBUG):
    json_data = JsonHandler.getAllJsonData()
    objects = []
    for object in json_data:
        name = object['name']
        price = extractPrice(object, DEBUG)
        new_object = {"name": name, "price": price}
        objects.append(new_object)
    return objects


