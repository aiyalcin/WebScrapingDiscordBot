import json
json_path = "Data/data.json"


def getAllJsonData():
    with open(json_path, "r") as file:
        loaded_data = json.load(file)['sites']
    return loaded_data


def getObject(id):
    try:
        with open(json_path, 'r') as file:
            data = json.load(file)

        for site in data['sites']:
            if site['id'] == id:
                return site

        print(f"No site found with ID {id}")
        return None
    except Exception as e:
        print(f"Error retrieving site: {e}")
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
        print(f"Error updating price in JSON file: {e}")

def addTracker(new_tracker):
    try:
        with open(json_path, 'r') as file:
            data = json.load(file)
        # Assign a new ID to the tracker
        new_id = max(site['id'] for site in data['sites']) + 1 if data['sites'] else 1
        new_tracker['id'] = new_id
        # Add the new tracker to the list
        data['sites'].append(new_tracker)
        # Write the updated data back to the file
        with open(json_path, 'w') as file:
            json.dump(data, file, indent=2)
    except Exception as e:
        print(f"Error adding tracker: {e}")

def removeTracker(id):
    try:
        with open(json_path, 'r') as file:
            data = json.load(file)

        # Filter out the site with the specified ID
        
        data['sites'] = [site for site in data['sites'] if site['id'] != id]
        # Write the updated data back to the file
        with open(json_path, 'w') as file:
            json.dump(data, file, indent=2)
    except Exception as e:
        print(f"Error removing tracker: {e}")