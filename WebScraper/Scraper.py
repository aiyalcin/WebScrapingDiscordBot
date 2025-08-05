from bs4 import BeautifulSoup
import requests
import re
from selenium import webdriver
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.common.by import By
import JsonHandler
import LogHandler as lh
import platform
import json
from urllib.parse import urlparse

if platform.system() == "Windows":
    GECKODRIVER_PATH = r"C:\Coding\Github\WebScrapingDiscordBot\WebScraper\bin\geckodriver\geckodriver.exe"
else:
    GECKODRIVER_PATH = "/usr/bin/geckodriver"

def get_site_html(url, selector, use_js):
    if use_js:
        options = webdriver.FirefoxOptions()
        options.add_argument('--headless')
        service = Service(GECKODRIVER_PATH)
        driver = webdriver.Firefox(service=service, options=options)
        driver.get(url)
        # Get the outer HTML of the element matching the selector
        try:
            price_element = driver.find_element(By.CSS_SELECTOR, selector)
            html = price_element.get_attribute('outerHTML')
        except Exception:
            html = driver.page_source
        driver.quit()
        return html
    else:
        return requests.get(url).text

async def extractPrice(object, DEBUG, guild_id=None, user_id=None, discord_notify=None):
    lh.log(f"Now scraping ID: {object['id']}", "log")
    try:
        url = object['url']
        selectors = object.get('selectors')
        if not selectors:
            selectors = [object.get('selector')]
        use_js = object.get('js', False)
        lh.log(f"Requesting URL: {url}", "log")
        html_text = get_site_html(url, selectors[0], use_js)
        if not html_text or len(html_text) < 100:
            lh.log(f"HTML response is empty or too short for {object['name']} price likely rendered with JavaScript", "warn")
        else:
            lh.log(f"HTML response length for {object['name']}: {len(html_text)}", "log")
        soup = BeautifulSoup(html_text, "lxml")
        price_element = None
        active_selector = None
        for sel in selectors:
            price_element = soup.select_one(sel)
            if price_element:
                active_selector = sel
                break
        if not price_element:
            domain = urlparse(url).netloc.replace('www.', '')
            try:
                with open('selector_data.json', 'r') as f:
                    selector_data = json.load(f)
                extra_selectors = selector_data.get(domain, [])
                for alt_selector in extra_selectors:
                    if alt_selector in selectors:
                        continue
                    price_element = soup.select_one(alt_selector)
                    if price_element:
                        active_selector = alt_selector
                        selectors.append(alt_selector)
                        break
            except Exception as e:
                lh.log(f"Error loading selector_data.json: {e}", "error")
        if not price_element:
            print(html_text)
            lh.log(f"Could not find price element for {object['name']} with any known selector. Item might be sold out or selector has changed.", "warn")
            # Discord notification logic
            if discord_notify:
                await discord_notify(object, user_id)
            return None
        price_text = price_element.get_text(strip=True)
        lh.log(f"Extracted price text for {object['name']}: '{price_text}'", "log")

        match = re.search(r'\d+(?:[.,]\d{2})?', price_text)
        if match:
            clean_price = match.group(0)
            lh.log(f"Cleaned price for {object['name']}: '{clean_price}'", "log")
        else:
            lh.log(f"Could not extract price from text: '{price_text}'", "error")
            return None

        # Update price and active_selector in the correct place
        object['active_selector'] = active_selector
        object['currentPrice'] = clean_price
        if guild_id is not None:
            JsonHandler.update_site_price(object['id'], clean_price, guild_id)
        elif user_id is not None:
            JsonHandler.update_user_tracker_price(user_id, object['id'], clean_price)

        return clean_price
    except Exception as e:
        lh.log(f"Error extracting price for {object.get('name', 'unknown')}: {e}", "error")
        return None


def getAllPrices(DEBUG, private_tracks_enabled, guild_id ,user_id=None):
    # Get tracker info only (not prices) from JSON
    if private_tracks_enabled and user_id:
        trackers = JsonHandler.getUserTrackers(user_id)
    else:
        trackers = JsonHandler.getAllJsonData(guild_id)
    objects = []
    for tracker in trackers:
        ID = tracker['id']
        name = tracker['name']
        # Scrape the current price from the web
        price = extractPrice(tracker, DEBUG)
        new_object = {"id": ID, "name": name, "price": price}
        objects.append(new_object)
    return objects





