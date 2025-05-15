import json
json_path = "Data/data.json"
import LogHandler as log

def addTracker(siteObject):
    # Load existing data
    with open('your_json_file.json', 'r') as f:
        data = json.load(f)

    # Find the highest current ID
    max_id = max(site['id'] for site in data['sites']) if data['sites'] else 0

    # Create new tracker with next ID
    new_tracker = {
        'id': max_id + 1,
        'name': siteObject['name'],
        'url': siteObject['url'],
        'selector': siteObject['selector'],
        'currentPrice': str(siteObject['currentPrice'])  # Convert to string to match your format
    }

    # Add the new tracker
    data['sites'].append(new_tracker)

    # Write back to file
    with open('your_json_file.json', 'w') as f:
        json.dump(data, f, indent=2)

def getAllJsonData():
    with open("Data/data.json", "r") as file:
        loaded_data = json.load(file)['sites']
    return loaded_data


def getObject(id):
    try:
        with open(json_path, 'r') as file:
            data = json.load(file)

        for site in data['sites']:
            if site['id'] == id:
                return site
        log.log_handler(f"No site found with ID {id}", "error")
        return None
    except Exception as e:
        log.log_handler(f"Error retrieving site: {e}", "error")
        return None


def update_site_price(site_id, new_price):
    try:
        # Read the entire JSON data
        with open(json_path, 'r') as file:
            data = json.load(file)

        # Find and update the specific site
        for site in data['sites']:
            if site['id'] == site_id:
                site['currentPrice'] = new_price
                break

        # Write the updated data back to the file
        with open(json_path, 'w') as file:
            json.dump(data, file, indent=2)

    except Exception as e:
        log.log_handler(f"Error updating price in JSON file: {e}", "error")
