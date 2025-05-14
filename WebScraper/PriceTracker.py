import JsonHandler
import Scraper
import LogHandler as log

def CheckPrices():
    json_objects = JsonHandler.getAllJsonData()
    price_objects = Scraper.getAllPrices()
    changed_prices = []
    for oldObject in json_objects:
        price_old = oldObject['currentPrice'].replace("€", "")

        for newObject in price_objects:
            if newObject['name'] == oldObject['name']:
                log.log_handler(f"New value: {newObject['price']}, OLD value: {price_old}", "log")
                if price_old != newObject['price']:
                    print("Changed price detected!")
                    changed_price_item = {"name": newObject['name'], "Old price": price_old, "New price": newObject['price']}
                    changed_prices.append(changed_price_item)
    print(len(changed_prices))
    if len(changed_prices) > 0:
        return changed_prices
    else:
        return None