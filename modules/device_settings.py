import requests
from dotenv import load_dotenv
from modules.blockchain import log_to_blockchain
import os

# Load environment variables
load_dotenv()

# Environment variables
SERVER_BASE_URL = os.getenv("SERVER_BASE_URL")
SERIAL_NUMBER = os.getenv("SERIAL_NUMBER")
DEVICE_API_KEY = os.getenv("DEVICE_API_KEY")

# Validate environment variables
if not SERVER_BASE_URL or not SERIAL_NUMBER or not DEVICE_API_KEY:
    raise ValueError("SERVER_BASE_URL, SERIAL_NUMBER, and DEVICE_API_KEY must be set in the environment variables.")

def fetch_user_and_device_settings():
    """
    Fetch user and device settings from the server.

    Returns:
        tuple: A tuple containing device settings and user settings dictionaries.
    """
    headers = {
        "x-api-key": DEVICE_API_KEY,
        "x-serial-number": SERIAL_NUMBER,
    }
    print("Fetching settings with headers:", headers)

    try:
        # Make GET request to fetch settings
        response = requests.get(
            f"{SERVER_BASE_URL}/api/devices/user-and-settings", 
            headers=headers, 
            timeout=10
        )
        response.raise_for_status()

        # Parse response
        data = response.json()
        log_to_blockchain("fetch_user_settings", data)  # Log settings fetch to blockchain
        print("Fetched user and device settings successfully.")

        # Return device and user settings
        return data.get("deviceSettings", {}), data.get("userSettings", {})

    except requests.HTTPError as e:
        if response.status_code == 401:
            print("Unauthorized: Invalid API key or serial number.")
        else:
            print(f"HTTP Error {response.status_code}: {response.text}")
        log_to_blockchain("error", {"action": "fetch_user_settings", "error": str(e)})
        return None, None

    except requests.RequestException as e:
        print(f"Request failed: {e}")
        log_to_blockchain("error", {"action": "fetch_user_settings", "error": str(e)})
        return None, None
