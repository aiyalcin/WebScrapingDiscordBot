import json
import os
import LogHandler as lh
import uuid
json_path = "data/data.json"
debug_json_path = "Data/debug_data.json"

# Helper to switch between normal and debug json

def get_active_json_path():
    if os.path.exists(debug_json_path):
        return debug_json_path
    return json_path

# Get all trackers (global or user)
def getAllJsonData(guild_id=None):
    with open(get_active_json_path(), "r") as file:
        data = json.load(file)
    if guild_id is None:
        # Return all user trackers as a flat list
        all_tracks = []
        for user_tracks in data.get('users', {}).values():
            all_tracks.extend(user_tracks)
        return all_tracks
    else:
        guild_id = str(guild_id)
        return data.get('global', {}).get(guild_id, [])

# For showMyTracks
def getUserTrackers(user_id):
    user_id = str(user_id)
    with open(get_active_json_path(), "r") as file:
        data = json.load(file)
    return data.get('users', {}).get(user_id, [])

# For adding a user tracker
# Now supports selectors and active_selector
def addUserTracker(user_id, new_tracker):
    user_id = str(user_id)
    with open(get_active_json_path(), 'r') as file:
        data = json.load(file)
    users = data.setdefault('users', {})
    user_tracks = users.setdefault(user_id, [])
    # Assign a new short ID (per user) and a UUID
    all_ids = [t['id'] for t in user_tracks]
    new_id = max(all_ids) + 1 if all_ids else 1
    new_tracker['id'] = new_id
    new_tracker['uuid'] = str(uuid.uuid4())
    # Ensure selectors and active_selector fields exist
    if 'selectors' not in new_tracker and 'selector' in new_tracker:
        new_tracker['selectors'] = [new_tracker['selector']]
        new_tracker['active_selector'] = new_tracker['selector']
        del new_tracker['selector']
    elif 'selectors' in new_tracker and 'active_selector' not in new_tracker:
        new_tracker['active_selector'] = new_tracker['selectors'][0] if new_tracker['selectors'] else None
    user_tracks.append(new_tracker)
    with open(get_active_json_path(), 'w') as file:
        json.dump(data, file, indent=2)

# For removing a user tracker
def removeUserTracker(user_id, id):
    user_id = str(user_id)
    with open(get_active_json_path(), 'r') as file:
        data = json.load(file)
    users = data.get('users', {})
    user_tracks = users.get(user_id, [])
    initial_len = len(user_tracks)
    user_tracks = [t for t in user_tracks if t['id'] != id]
    users[user_id] = user_tracks
    with open(get_active_json_path(), 'w') as file:
        json.dump(data, file, indent=2)
    return len(user_tracks) < initial_len

# For getting a global tracker object by id
def getObject(id, guild_id):
    try:
        with open(get_active_json_path(), 'r') as file:
            data = json.load(file)
        for site in data.get('global', {}).get(guild_id, []):
            if site['id'] == id:
                return site
        lh.log(f"No site found with ID {id} in guild {guild_id}", "warn")
        return None
    except Exception as e:
        lh.log(f"Error retrieving site: {e}", "error")
        return None

# For updating a global tracker price
def update_site_price(site_id, new_price, guild_id):
    try:
        with open(get_active_json_path(), 'r') as file:
            data = json.load(file)
        for site in data.get('global', {}).get(guild_id, []):
            if site['id'] == site_id:
                site['currentPrice'] = new_price
                break
        with open(get_active_json_path(), 'w') as file:
            json.dump(data, file, indent=2)
    except Exception as e:
        lh.log(f"Error updating price in JSON file: {e}", "error")

# For adding a global tracker
# Now supports selectors and active_selector
def addTracker(new_tracker, guild_id):
    try:
        with open(get_active_json_path(), 'r') as file:
            data = json.load(file)
        global_trackers = data.setdefault('global', {})
        guild_trackers = global_trackers.setdefault(guild_id, [])
        # Assign a new short ID (per guild) and a UUID
        new_id = max([site['id'] for site in guild_trackers], default=0) + 1
        new_tracker['id'] = new_id
        new_tracker['uuid'] = str(uuid.uuid4())
        # Ensure selectors and active_selector fields exist
        if 'selectors' not in new_tracker and 'selector' in new_tracker:
            new_tracker['selectors'] = [new_tracker['selector']]
            new_tracker['active_selector'] = new_tracker['selector']
            del new_tracker['selector']
        elif 'selectors' in new_tracker and 'active_selector' not in new_tracker:
            new_tracker['active_selector'] = new_tracker['selectors'][0] if new_tracker['selectors'] else None
        guild_trackers.append(new_tracker)
        with open(get_active_json_path(), 'w') as file:
            json.dump(data, file, indent=2)
    except Exception as e:
        lh.log(f"Error adding tracker: {e}", "error")

# For removing a global tracker
def removeTracker(id, guild_id):
    try:
        with open(get_active_json_path(), 'r') as file:
            data = json.load(file)
        guild_trackers = data.get('global', {}).get(guild_id, [])
        data['global'][guild_id] = [site for site in guild_trackers if site['id'] != id]
        with open(get_active_json_path(), 'w') as file:
            json.dump(data, file, indent=2)
    except Exception as e:
        lh.log(f"Error removing tracker: {e}", "error")

def update_user_tracker_price(user_id, site_id, new_price):
    user_id = str(user_id)
    try:
        with open(get_active_json_path(), 'r') as file:
            data = json.load(file)
        user_tracks = data.get('users', {}).get(user_id, [])
        for tracker in user_tracks:
            if tracker['id'] == site_id:
                tracker['currentPrice'] = new_price
                break
        with open(get_active_json_path(), 'w') as file:
            json.dump(data, file, indent=2)
    except Exception as e:
        lh.log(f"Error updating user tracker price: {e}", "error")

# Update the name of a user tracker by user_id and site_id
def update_user_tracker_name(user_id, site_id, new_name):
    user_id = str(user_id)
    try:
        with open(get_active_json_path(), 'r') as file:
            data = json.load(file)
        user_tracks = data.get('users', {}).get(user_id, [])
        for tracker in user_tracks:
            if tracker['id'] == site_id:
                tracker['name'] = new_name
        with open(get_active_json_path(), 'w') as file:
            json.dump(data, file, indent=2)
    except Exception as e:
        lh.log(f"Error updating user tracker name: {e}", "error")