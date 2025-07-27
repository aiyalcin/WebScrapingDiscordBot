import json
import os
json_path = "data/data.json"
debug_json_path = "Data/debug_data.json"

# Helper to switch between normal and debug json

def get_active_json_path():
    if os.path.exists(debug_json_path):
        return debug_json_path
    return json_path

# Get all trackers (global or user)
def getAllJsonData(private_tracks_enabled, guild_id=None):
    with open(get_active_json_path(), "r") as file:
        data = json.load(file)
    if private_tracks_enabled:
        # Return all user trackers as a flat list
        all_tracks = []
        for user_tracks in data.get('users', {}).values():
            all_tracks.extend(user_tracks)
        return all_tracks
    else:
        if guild_id is None:
            return []
        return data.get('global', {}).get(guild_id, [])

# For showMyTracks
def getUserTrackers(username):
    with open(get_active_json_path(), "r") as file:
        data = json.load(file)
    return data.get('users', {}).get(username, [])

# For adding a user tracker
def addUserTracker(username, new_tracker):
    with open(get_active_json_path(), 'r') as file:
        data = json.load(file)
    users = data.setdefault('users', {})
    user_tracks = users.setdefault(username, [])
    # Assign a new ID
    all_ids = [t['id'] for tracks in users.values() for t in tracks]
    new_id = max(all_ids) + 1 if all_ids else 1
    new_tracker['id'] = new_id
    user_tracks.append(new_tracker)
    with open(get_active_json_path(), 'w') as file:
        json.dump(data, file, indent=2)

# For removing a user tracker
def removeUserTracker(username, id):
    with open(get_active_json_path(), 'r') as file:
        data = json.load(file)
    users = data.get('users', {})
    user_tracks = users.get(username, [])
    initial_len = len(user_tracks)
    user_tracks = [t for t in user_tracks if t['id'] != id]
    users[username] = user_tracks
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
        print(f"No site found with ID {id} in guild {guild_id}")
        return None
    except Exception as e:
        print(f"Error retrieving site: {e}")
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
        print(f"Error updating price in JSON file: {e}")

# For adding a global tracker
def addTracker(new_tracker, guild_id):
    try:
        with open(get_active_json_path(), 'r') as file:
            data = json.load(file)
        global_trackers = data.setdefault('global', {})
        guild_trackers = global_trackers.setdefault(guild_id, [])
        # Assign a new ID to the tracker
        new_id = max([site['id'] for site in guild_trackers], default=0) + 1
        new_tracker['id'] = new_id
        guild_trackers.append(new_tracker)
        with open(get_active_json_path(), 'w') as file:
            json.dump(data, file, indent=2)
    except Exception as e:
        print(f"Error adding tracker: {e}")

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
        print(f"Error removing tracker: {e}")

def update_user_tracker_price(username, site_id, new_price):
    try:
        with open(get_active_json_path(), 'r') as file:
            data = json.load(file)
        user_tracks = data.get('users', {}).get(username, [])
        for tracker in user_tracks:
            if tracker['id'] == site_id:
                tracker['currentPrice'] = new_price
                break
        with open(get_active_json_path(), 'w') as file:
            json.dump(data, file, indent=2)
    except Exception as e:
        print(f"Error updating user tracker price: {e}")