import json
import os
from datetime import datetime, timedelta, timezone

API_KEYS_FILE = "/home/bestapikey/api_keys.json"

DEFAULT_DAILY_LIMIT = 1500
DEFAULT_MINUTE_LIMIT = 15

def load_api_keys(file_path=API_KEYS_FILE):
    """Load API keys from a JSON file."""
    if not os.path.exists(file_path):
        return []
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_api_keys(api_keys, file_path=API_KEYS_FILE):
    """Save the updated list of API keys to a JSON file."""
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(api_keys, f, indent=2)

def reset_if_needed(api_key_dict):
    """
    Check if we need to reset daily or per-minute usage for the given key:
      - If a new day has started, reset `day_usage` to 0 and update `day_reset_date`.
      - If the minute window (60 seconds) has passed since `minute_reset_time`, reset `minute_usage`.
    """
    now_utc = datetime.now(timezone.utc)
    
    # --- 1) Daily usage reset if current date changed ---
    today_str = now_utc.date().isoformat()  # e.g. '2025-02-23'
    if api_key_dict.get("day_reset_date") is None:
        # Initialize if not present
        api_key_dict["day_reset_date"] = today_str
        api_key_dict["day_usage"] = 0
    else:
        if api_key_dict["day_reset_date"] != today_str:
            api_key_dict["day_usage"] = 0
            api_key_dict["day_reset_date"] = today_str

    # --- 2) Minute usage reset if 60+ seconds have passed ---
    if api_key_dict.get("minute_reset_time") is None:
        # Initialize if not present
        api_key_dict["minute_reset_time"] = now_utc.isoformat()
        api_key_dict["minute_usage"] = 0
    else:
        reset_time = datetime.fromisoformat(api_key_dict["minute_reset_time"])
        if (now_utc - reset_time) >= timedelta(seconds=60):
            api_key_dict["minute_usage"] = 0
            api_key_dict["minute_reset_time"] = now_utc.isoformat()

def is_under_limit(api_key_dict, daily_limit=DEFAULT_DAILY_LIMIT, minute_limit=DEFAULT_MINUTE_LIMIT):
    """
    Check if the given API key is under both daily and per-minute limits.
    Return True if under limit, False otherwise.
    """
    # Make sure the usage counters are up-to-date
    reset_if_needed(api_key_dict)

    if api_key_dict.get("day_usage", 0) >= daily_limit:
        return False
    if api_key_dict.get("minute_usage", 0) >= minute_limit:
        return False
    return True

def get_best_key(api_keys, daily_limit=DEFAULT_DAILY_LIMIT, minute_limit=DEFAULT_MINUTE_LIMIT):
    """
    Return the 'best' key among those that have not exceeded the daily or per-minute limit.
    'Best' = the one with the fewest total requests, then oldest last_request_time as tiebreaker.
    """
    valid_keys = [k for k in api_keys if is_under_limit(k, daily_limit, minute_limit)]
    if not valid_keys:
        return None  # All keys are over limit or none exist

    def sort_key(k):
        requests_count = k.get("requests", 0)
        last_request = k.get("last_request_time")
        if last_request is None:
            last_request_dt = datetime.min.replace(tzinfo=timezone.utc)
        else:
            last_request_dt = datetime.fromisoformat(last_request)
        return (requests_count, last_request_dt)
    
    best = sorted(valid_keys, key=sort_key)[0]
    return best

def update_key_usage(api_key_dict):
    """
    Increment usage counters (total requests, daily usage, minute usage)
    and update last_request_time. Make sure daily/minute usage is reset if needed first.
    """
    reset_if_needed(api_key_dict)
    now_utc = datetime.now(timezone.utc)

    api_key_dict["requests"] = api_key_dict.get("requests", 0) + 1
    api_key_dict["day_usage"] = api_key_dict.get("day_usage", 0) + 1
    api_key_dict["minute_usage"] = api_key_dict.get("minute_usage", 0) + 1
    api_key_dict["last_request_time"] = now_utc.isoformat()

def get_and_use_best_key(daily_limit=DEFAULT_DAILY_LIMIT, minute_limit=DEFAULT_MINUTE_LIMIT):
    """
    Main function to load all keys, pick the best under the limit, update it, save changes,
    and return the key string for an API call.
    """
    api_keys = load_api_keys()
    if not api_keys:
        print("No API keys available.")
        return None
    
    best = get_best_key(api_keys, daily_limit, minute_limit)
    if not best:
        print("No API keys are under the usage limits.")
        return None
    
    update_key_usage(best)
    save_api_keys(api_keys)
    return best["key"]


# --------------------------------------------------------------------------------
# NEW FUNCTIONS: Adding and removing API keys
# --------------------------------------------------------------------------------

def add_api_key(new_key):
    """
    Add a new API key if it does not already exist.
    Initialize default usage counters.
    Returns True if key was added, False if it already existed.
    """
    api_keys = load_api_keys()

    # Check if the key already exists
    for k in api_keys:
        if k["key"] == new_key:
            print(f"API key '{new_key}' already exists.")
            return False
    
    # If not found, add a new entry with default usage
    new_key_dict = {
        "key": new_key,
        "requests": 0,
        "last_request_time": None,
        "minute_usage": 0,
        "minute_reset_time": None,
        "day_usage": 0,
        "day_reset_date": None
    }
    api_keys.append(new_key_dict)
    save_api_keys(api_keys)
    print(f"API key '{new_key}' added successfully.")
    return True

def remove_api_key(key_to_remove):
    """
    Remove an API key from the JSON file if it exists.
    Returns True if key was removed, False if it wasn't found.
    """
    api_keys = load_api_keys()
    original_length = len(api_keys)
    
    # Keep all keys that do NOT match the one we want to remove
    api_keys = [k for k in api_keys if k["key"] != key_to_remove]
    
    if len(api_keys) == original_length:
        # Means we didn't remove anything
        print(f"API key '{key_to_remove}' not found. No changes made.")
        return False
    
    # Otherwise, we removed the key
    save_api_keys(api_keys)
    print(f"API key '{key_to_remove}' removed successfully.")
    return True


# --------------------------------------------------------------------------------
# Example Usage
# --------------------------------------------------------------------------------
if __name__ == "__main__":
    # 1. Add a new key
    add_api_key("my_new_api_key_123")
    
    # 2. Get and use the best key
    chosen_key = get_and_use_best_key()
    if chosen_key:
        print(f"\nChosen key for this request: {chosen_key}\n")
    
    # 3. Remove the key
    remove_api_key("my_new_api_key_123")
