import JsonHandler
import Scraper
import json
import LogHandler as lh
import asyncio

# Define semaphores for concurrency limits
SELENIUM_LIMIT = 2
HTML_LIMIT = 4
selenium_semaphore = asyncio.Semaphore(SELENIUM_LIMIT)
html_semaphore = asyncio.Semaphore(HTML_LIMIT)

async def retry_async(coro_func, *args, retries=2, delay=2, **kwargs):
    for attempt in range(retries):
        result = await coro_func(*args, **kwargs)
        if result is not None:
            return result
        if attempt < retries - 1:
            await asyncio.sleep(delay)
    return None

async def limited_extract_price(tracker, DEBUG, guild_id, user_id, discord_notify):
    js_needed = tracker.get('js', False)
    if js_needed:
        async with selenium_semaphore:
            return await Scraper.extractPrice(tracker, DEBUG, guild_id=guild_id, user_id=user_id, discord_notify=discord_notify)
    else:
        async with html_semaphore:
            return await Scraper.extractPrice(tracker, DEBUG, guild_id=guild_id, user_id=user_id, discord_notify=discord_notify)

async def CheckPrivateTrackers(DEBUG, discord_notify=None):
    """Check all private trackers for price changes and return a list of changes."""
    changed_prices = []
    user_ids = JsonHandler.get_all_user_ids()
    tasks = []
    tracker_refs = []
    for user_id in user_ids:
        user_trackers = JsonHandler.getUserTrackers(user_id)
        seen = set()
        unique_trackers = []
        for tracker in user_trackers:
            key = (tracker['url'], tracker['selector'])
            if key not in seen:
                seen.add(key)
                unique_trackers.append(tracker)
        for tracker in unique_trackers:
            tasks.append(
                limited_extract_price(tracker, DEBUG, guild_id=None, user_id=user_id, discord_notify=discord_notify)
            )
            tracker_refs.append((tracker, user_id))
    scraped_prices = await asyncio.gather(*tasks)
    # Retry failed (None) scrapes
    retry_tasks = []
    retry_refs = []
    for (ref, result) in zip(tracker_refs, scraped_prices):
        if result is None:
            tracker, user_id = ref
            retry_tasks.append(retry_async(
                limited_extract_price, tracker, DEBUG, guild_id=None, user_id=user_id, discord_notify=discord_notify
            ))
            retry_refs.append(ref)
    if retry_tasks:
        retry_results = await asyncio.gather(*retry_tasks)
        for idx, (ref, retry_result) in enumerate(zip(retry_refs, retry_results)):
            i = tracker_refs.index(ref)
            scraped_prices[i] = retry_result
    # Compare scraped prices to stored prices
    for (old, user_id), new_price in zip(tracker_refs, scraped_prices):
        price_old = old['currentPrice'].replace("€", "")
        lh.log(f"Tracker ID: {old['id']} | Old price: {price_old} | Scraped price: {new_price}", "log")
        if price_old != new_price:
            lh.log("Changed price detected!", "success")
            changed_prices.append({
                "name": old['name'],
                "Old price": price_old,
                "New price": new_price,
                "user_id": user_id,
                "id": old['id']
            })
    return changed_prices if changed_prices else None

async def CheckGlobalTrackers(DEBUG, guild_id, discord_notify=None):
    """Check all global trackers for price changes and return a list of changes."""
    changed_prices = []
    guild_id = str(guild_id)
    json_objects = JsonHandler.getAllJsonData(guild_id)
    tasks = []
    tracker_refs = []
    for tracker in json_objects:
        tasks.append(
            limited_extract_price(tracker, DEBUG, guild_id=guild_id, user_id=None, discord_notify=discord_notify)
        )
        tracker_refs.append(tracker)
    scraped_prices = await asyncio.gather(*tasks)
    # Retry failed (None) scrapes
    retry_tasks = []
    retry_refs = []
    for (ref, result) in zip(tracker_refs, scraped_prices):
        if result is None:
            retry_tasks.append(retry_async(
                limited_extract_price, ref, DEBUG, guild_id=guild_id, user_id=None, discord_notify=discord_notify
            ))
            retry_refs.append(ref)
    if retry_tasks:
        retry_results = await asyncio.gather(*retry_tasks)
        for idx, (ref, retry_result) in enumerate(zip(retry_refs, retry_results)):
            i = tracker_refs.index(ref)
            scraped_prices[i] = retry_result
    # Compare scraped prices to stored prices
    for old, new_price in zip(tracker_refs, scraped_prices):
        price_old = old['currentPrice'].replace("€", "")
        lh.log(f"Tracker ID: {old['id']} | Old price: {price_old} | Scraped price: {new_price}", "log")
        if new_price is not None and price_old != new_price:
            lh.log("Changed price detected!", "success")
            changed_prices.append({
                "name": old['name'],
                "Old price": price_old,
                "New price": new_price
            })
        elif new_price is None:
            changed_prices.append({
                "name": old['name'],
                "Old price": price_old,
                "New price": None
            })
    return changed_prices if changed_prices else None
