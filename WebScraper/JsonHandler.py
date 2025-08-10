import json
import os
import LogHandler as lh
import uuid

CONFIG_PATH = "config/guild_config.json"
path_dataJson = "data/data.json"
path_selectorDataJson = "data/selector_data.json"
debug_json_path = "data/debug_data.json"
USER_PERMS_PATH = "data/user_perms.json"
MAX_GLOBAL_TRACKERS_PER_GUILD = 20
DEFAULT_TRACKER_LIMIT = 5 

# Helper: get per-user tracker limit, using exceptions in user_perms.json
def get_user_tracker_limit(user_id):
    try:
        with open(USER_PERMS_PATH, "r") as file:
            perms = json.load(file)
        return perms.get("user_limits", {}).get(str(user_id), DEFAULT_TRACKER_LIMIT)
    except Exception:
        return DEFAULT_TRACKER_LIMIT

# Helper: check if user is banned (limit 0 means banned)
def is_user_banned(user_id):
    return get_user_tracker_limit(user_id) == 0

# For adding a user tracker (now uses per-user limit and ban check)
def addUserTracker(user_id, new_tracker):
    user_id = str(user_id)
    if is_user_banned(user_id):
        return False
    with open(get_active_json_path(), 'r') as file:
        data = json.load(file)
    users = data.setdefault('users', {})
    user_tracks = users.setdefault(user_id, [])
    limit = get_user_tracker_limit(user_id)
    if len(user_tracks) >= limit:
        return False
    all_ids = [t['id'] for t in user_tracks]
    new_id = max(all_ids) + 1 if all_ids else 1
    new_tracker['id'] = new_id
    new_tracker['uuid'] = str(uuid.uuid4())
    user_tracks.append(new_tracker)
    with open(get_active_json_path(), 'w') as file:
        json.dump(data, file, indent=2)
    return True

def get_all_user_ids():
    with open(get_active_json_path(), "r") as file:
        data = json.load(file)
    return list(data.get('users', {}).keys())

def get_active_json_path():
    if os.path.exists(debug_json_path):
        return debug_json_path
    return path_dataJson

def load_guild_config():
    if not os.path.exists(CONFIG_PATH):
        return {}
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)

def save_guild_config(config):
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)

def load_selector_data():
    if not os.path.exists(path_selectorDataJson):
        return {}
    with open(path_selectorDataJson, "r") as f:
        return json.load(f)

def save_selector_data(data):
    with open(path_selectorDataJson, "w") as f:
        json.dump(data, f, indent=2)

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
def addTracker(new_tracker, guild_id):
    try:
        with open(get_active_json_path(), 'r') as file:
            data = json.load(file)
        global_trackers = data.setdefault('global', {})
        guild_trackers = global_trackers.setdefault(guild_id, [])
        if len(guild_trackers) >= MAX_GLOBAL_TRACKERS_PER_GUILD:
            return False
        new_id = max([site['id'] for site in guild_trackers], default=0) + 1
        new_tracker['id'] = new_id
        new_tracker['uuid'] = str(uuid.uuid4())
        guild_trackers.append(new_tracker)
        with open(get_active_json_path(), 'w') as file:
            json.dump(data, file, indent=2)
        return True
    except Exception as e:
        lh.log(f"Error adding tracker: {e}", "error")
        return False

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

def get_selector_data():
    if not os.path.exists(path_selectorDataJson):
        return {}
    with open(path_selectorDataJson, "r", encoding="utf-8") as f:
        return json.load(f)

def update_user_tracker_name(user_id, tracker_id, new_name):
    user_id = str(user_id)
    try:
        with open(get_active_json_path(), 'r') as file:
            data = json.load(file)
        user_tracks = data.get('users', {}).get(user_id, [])
        for tracker in user_tracks:
            if tracker['id'] == tracker_id:
                tracker['name'] = new_name
                break
        with open(get_active_json_path(), 'w') as file:
            json.dump(data, file, indent=2)
    except Exception as e:
        lh.log(f"Error updating tracker name for user {user_id}, tracker {tracker_id}: {e}", "error")

