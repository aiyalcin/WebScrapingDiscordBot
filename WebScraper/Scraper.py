from bs4 import BeautifulSoup
import requests
import JsonHandler
import PriceTracker


def extractPrice(object):
    print(f"Now scraping ID: {object['id']}")
    try:
        url = object['url']
        selector = object['selector']
        html_text = requests.get(url).text
        soup = BeautifulSoup(html_text, "lxml")
        price_element = soup.select_one(selector)

        if not price_element:
            print(f"Could not find price element for {object['name']}")
            return None

        new_price_text = price_element.getText(strip=True).replace("€", "").replace(" ", "")

        JsonHandler.update_site_price(object['id'], new_price_text)

        return new_price_text
    except Exception as e:
        print(f"Error extracting price for {object.get('name', 'unknown')}: {e}")
        return None



def getAllPrices():
    json_data = JsonHandler.getAllJsonData()
    objects = []
    for object in json_data:
        name = object['name']
        price = extractPrice(object)
        new_object = {"name": name, "price": price}
        objects.append(new_object)
    return objects


