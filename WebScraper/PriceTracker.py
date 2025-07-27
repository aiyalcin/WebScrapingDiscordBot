import JsonHandler
import Scraper
import json


def get_all_usernames():
    with open(JsonHandler.json_path, "r") as file:
        data = json.load(file)
    return list(data.get('users', {}).keys())


def CheckPrices(DEBUG, private_tracks_enabled):
    changed_prices = []
    if private_tracks_enabled:
        usernames = get_all_usernames()
        for username in usernames:
            user_trackers = JsonHandler.getUserTrackers(username)
            # Scrape prices for this user's trackers only
            scraped_prices = []
            for tracker in user_trackers:
                scraped_price = Scraper.extractPrice(tracker, DEBUG, guild_id=None, username=username)
                scraped_prices.append({"id": tracker['id'], "name": tracker['name'], "price": scraped_price})
            # Compare scraped prices to stored prices
            for oldObject in user_trackers:
                price_old = oldObject['currentPrice'].replace("€", "")
                for newObject in scraped_prices:
                    if newObject['id'] == oldObject['id']:
                        print(f"Scraped value: {newObject['price']} Value in data.json: {price_old}")
                        if price_old != newObject['price']:
                            print("Changed price detected!")
                            changed_price_item = {"name": newObject['name'], "Old price": price_old, "New price": newObject['price'], "user": username}
                            changed_prices.append(changed_price_item)
    else:
        json_objects = JsonHandler.getAllJsonData(False)
        scraped_prices = []
        for tracker in json_objects:
            # You need to know the guild_id for global trackers
            # Assume tracker has 'guild_id' or pass it in from caller
            guild_id = tracker.get('guild_id')
            scraped_price = Scraper.extractPrice(tracker, DEBUG, guild_id=guild_id)
            scraped_prices.append({"id": tracker['id'], "name": tracker['name'], "price": scraped_price})
        for oldObject in json_objects:
            price_old = oldObject['currentPrice'].replace("€", "")
            for newObject in scraped_prices:
                if newObject['id'] == oldObject['id']:
                    print(f"Scraped value: {newObject['price']} Value in data.json: {price_old}")
                    if price_old != newObject['price']:
                        print("Changed price detected!")
                        changed_price_item = {"name": newObject['name'], "Old price": price_old, "New price": newObject['price']}
                        changed_prices.append(changed_price_item)
    print(len(changed_prices))
    if len(changed_prices) > 0:
        return changed_prices
    else:
        return None
