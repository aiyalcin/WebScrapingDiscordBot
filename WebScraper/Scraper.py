from bs4 import BeautifulSoup
import requests
import JsonHandler
import PriceTracker
import LogHandler as lh

def extractPrice(object, DEBUG):
    lh.log(f"Now scraping ID: {object['id']}", "log")
    try:
        url = object['url']
        selector = object['selector']
        html_text = requests.get(url).text
        soup = BeautifulSoup(html_text, "lxml")
        price_element = soup.select_one(selector)

        if not price_element:
            lh.log(f"Could not find price element for {object['name']}", "error")
            return None

        new_price_text = price_element.getText(strip=True).replace("€", "").replace(" ", "")

        if not DEBUG:
            JsonHandler.update_site_price(object['id'], new_price_text)
        else:
            lh.log("Skipping write DEBUG is enabled", "warn")

        return new_price_text
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


