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
import asyncio
from AutoDetectPrice import clean_price_text
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

if platform.system() == "Windows":
    GECKODRIVER_PATH = r"C:\\Coding\\Github\\WebScrapingDiscordBot\\WebScraper\\bin\\geckodriver\\geckodriver.exe"
else:
    GECKODRIVER_PATH = "/usr/bin/geckodriver"

def get_site_html(url, selector, use_js):
    if use_js:
        options = webdriver.FirefoxOptions()
        options.add_argument('--headless')
        service = Service(GECKODRIVER_PATH)
        driver = webdriver.Firefox(service=service, options=options)
        driver.get(url)
        try:
            # Wait until the element has non-empty text
            price_element = WebDriverWait(driver, 10).until(
            EC.text_to_be_present_in_element((By.CSS_SELECTOR, selector), ""))
            # Now actually grab the element again
            price_element = driver.find_element(By.CSS_SELECTOR, selector)
            price_text = price_element.text
        except Exception:
            html = driver.page_source
        driver.quit()
        return html
    else:
        return requests.get(url).text

async def extractPrice(object, DEBUG, guild_id=None, user_id=None, discord_notify=None, loop=None):
    def blocking_scrape():
        lh.log(f"Now scraping ID: {object['id']}", "log")
        try:
            url = object['url']
            selector = object['selector']
            use_js = object.get('js', False)
            lh.log(f"Requesting URL: {url}", "log")
            html_text = get_site_html(url, selector, use_js)
            if not html_text or len(html_text) < 100:
                lh.log(f"HTML response is empty or too short for {object['name']} price likely rendered with JavaScript", "warn")
            else:
                lh.log(f"HTML response length for {object['name']}: {len(html_text)}", "log")
            soup = BeautifulSoup(html_text, "lxml")
            lh.log(f"Using selector: {selector}", "log")
            price_element = soup.select_one(selector)
            # If not found, try all known selectors for the domain, update selector if found
            if not price_element:
                domain = urlparse(url).netloc.replace('www.', '')
                selector_data = JsonHandler.get_selector_data()
                entry = selector_data.get(domain, {})
                selectors = entry.get("selectors", []) if isinstance(entry, dict) else entry
                js_required = entry.get("js", use_js) if isinstance(entry, dict) else use_js
                for alt_selector in selectors:
                    if alt_selector == selector:
                        continue
                    html_text_alt = get_site_html(url, alt_selector, js_required)
                    soup_alt = BeautifulSoup(html_text_alt, "lxml")
                    price_element = soup_alt.select_one(alt_selector)
                    if price_element:
                        selector = alt_selector
                        # Update the selector in the data file safely
                        data_path = JsonHandler.get_active_json_path()
                        with open(data_path, 'r') as f:
                            data = json.load(f)
                        updated = False
                        if guild_id is not None:
                            for site in data.get('global', {}).get(str(guild_id), []):
                                if site['id'] == object['id']:
                                    site['selector'] = selector
                                    updated = True
                                    break
                        elif user_id is not None:
                            for tracker in data.get('users', {}).get(str(user_id), []):
                                if tracker['id'] == object['id']:
                                    tracker['selector'] = selector
                                    updated = True
                                    break
                        if updated:
                            with open(data_path, 'w') as f:
                                json.dump(data, f, indent=2)
                        break
            if not price_element:
                lh.log(f"Could not find price element for {object['name']} with any known selector. Item might be sold out, on sale, or the selector has changed.", "warn")
                if discord_notify:
                    _loop = loop
                    if _loop is None:
                        try:
                            _loop = asyncio.get_running_loop()
                        except RuntimeError:
                            _loop = None
                    if _loop:
                        asyncio.run_coroutine_threadsafe(discord_notify(object, user_id), _loop)
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
            if guild_id is not None:
                JsonHandler.update_site_price(object['id'], clean_price, guild_id)
            elif user_id is not None:
                JsonHandler.update_user_tracker_price(user_id, object['id'], clean_price)
            return clean_price
        except Exception as e:
            lh.log(f"Error extracting price for {object.get('name', 'unknown')}: {e}", "error")
            return None
    return await asyncio.to_thread(blocking_scrape)

def selector_works_without_js(url, selector, expected_price):
    """Try to fetch the price with requests/BeautifulSoup and compare, with cleaning and logging."""
    lh.log(f"Checking if selector works without JS for URL: {url}", "log")
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code != 200:
            lh.log(f"Failed to fetch page (status {resp.status_code}) for {url}", "warn")
            return False
        soup = BeautifulSoup(resp.text, "lxml")
        el = soup.select_one(selector)
        if el and el.get_text(strip=True):
            found_price = el.get_text(strip=True)
            cleaned_found = clean_price_text(found_price)
            cleaned_expected = clean_price_text(expected_price)
            lh.log(f"Selector '{selector}' found price: '{found_price}' (cleaned: '{cleaned_found}', expected: '{expected_price}', cleaned expected: '{cleaned_expected}')", "log")
            if cleaned_found == cleaned_expected:
                lh.log("Selector works without JS (cleaned price matches).", "success")
                return True
            else:
                lh.log("Selector found price without JS, but cleaned value does not match expected.", "warn")
        else:
            lh.log(f"Selector '{selector}' did not find a price without JS.", "warn")
    except Exception as e:
        lh.log(f"Exception during non-JS selector check: {e}", "error")
    return False

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









