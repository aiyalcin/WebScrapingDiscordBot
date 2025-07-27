from bs4 import BeautifulSoup
import requests
import re
from selenium import webdriver
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.common.by import By
import JsonHandler
import LogHandler as lh
import platform

if platform.system() == "Windows":
    GECKODRIVER_PATH = r"C:\Coding\Github\WebScrapingDiscordBot\WebScraper\bin\geckodriver\geckodriver.exe"
else:
    GECKODRIVER_PATH = "/usr/bin/geckodriver"

def extractPrice(object, DEBUG, guild_id=None, username=None):
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

        # Update price in the correct place
        if guild_id is not None:
            JsonHandler.update_site_price(object['id'], clean_price, guild_id)
        elif username is not None:
            JsonHandler.update_user_tracker_price(username, object['id'], clean_price)

        return clean_price
    except Exception as e:
        lh.log(f"Error extracting price for {object.get('name', 'unknown')}: {e}", "error")
        return None


def getAllPrices(DEBUG, private_tracks_enabled, username=None):
    # Get tracker info only (not prices) from JSON
    if private_tracks_enabled and username:
        trackers = JsonHandler.getUserTrackers(username)
    else:
        trackers = JsonHandler.getAllJsonData(private_tracks_enabled)
    objects = []
    for tracker in trackers:
        ID = tracker['id']
        name = tracker['name']
        # Scrape the current price from the web
        price = extractPrice(tracker, DEBUG)
        new_object = {"id": ID, "name": name, "price": price}
        objects.append(new_object)
    return objects


