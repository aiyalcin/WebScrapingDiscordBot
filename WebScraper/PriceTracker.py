import JsonHandler
import Scraper
import json
import LogHandler as lh

def get_all_usernames():
    with open(JsonHandler.json_path, "r") as file:
        data = json.load(file)
    return list(data.get('users', {}).keys())


def CheckPrivateTrackers(DEBUG):
    changed_prices = []
    usernames = get_all_usernames()
    for username in usernames:
        user_trackers = JsonHandler.getUserTrackers(username)
        # Deduplicate trackers by (url, selector)
        seen = set()
        unique_trackers = []
        for tracker in user_trackers:
            key = (tracker['url'], tracker['selector'])
            if key not in seen:
                seen.add(key)
                unique_trackers.append(tracker)
        # Scrape prices for unique trackers only
        scraped_prices = []
        for tracker in unique_trackers:
            scraped_price = Scraper.extractPrice(tracker, DEBUG, guild_id=None, username=username)
            scraped_prices.append({"id": tracker['id'], "name": tracker['name'], "price": scraped_price})
        # Compare scraped prices to stored prices
        for oldObject in unique_trackers:
            price_old = oldObject['currentPrice'].replace("€", "")
            for newObject in scraped_prices:
                if newObject['id'] == oldObject['id']:
                    lh.log(f"Scraped value: {newObject['price']} Value in data.json: {price_old}", "log")
                    if price_old != newObject['price']:
                        lh.log("Changed price detected!", "success")
                        changed_price_item = {"name": newObject['name'], "Old price": price_old, "New price": newObject['price'], "user": username}
                        changed_prices.append(changed_price_item)
    if len(changed_prices) > 0:
        return changed_prices
    else:
        return None


def CheckGlobalTrackers(DEBUG, guild_id):
    changed_prices = []
    guild_id = str(guild_id)
    json_objects = JsonHandler.getAllJsonData(guild_id)
    scraped_prices = []
    for tracker in json_objects:
        scraped_price = Scraper.extractPrice(tracker, DEBUG, guild_id=guild_id)
        scraped_prices.append({"id": tracker['id'], "name": tracker['name'], "price": scraped_price})
    for oldObject in json_objects:
        price_old = oldObject['currentPrice'].replace("€", "")
        for newObject in scraped_prices:
            if newObject['id'] == oldObject['id']:
                lh.log(f"Scraped value: {newObject['price']} Value in data.json: {price_old}", "log")
                if price_old != newObject['price']:
                    lh.log("Changed price detected!", "success")
                    changed_price_item = {"name": newObject['name'], "Old price": price_old, "New price": newObject['price']}
                    changed_prices.append(changed_price_item)
    if len(changed_prices) > 0:
        return changed_prices
    else:
        return None
