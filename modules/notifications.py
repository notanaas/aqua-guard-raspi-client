import os
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Environment variables
SERVER_BASE_URL = os.getenv("SERVER_BASE_URL")
SERIAL_NUMBER = os.getenv("SERIAL_NUMBER")
DEVICE_API_KEY = os.getenv("DEVICE_API_KEY")

if not SERVER_BASE_URL or not SERIAL_NUMBER or not DEVICE_API_KEY:
    raise ValueError("SERVER_BASE_URL, SERIAL_NUMBER, and DEVICE_API_KEY must be set in the environment variables.")

def notify_server(user_identifier, message, notification_type="info"):
    """
    Send a notification to the server.

    Parameters:
        user_identifier (str): Username, email, or ID of the user.
        message (str): Notification message.
        notification_type (str): Type of notification (e.g., 'info', 'warning', 'error').
    """
    headers = {
        "x-serial-number": SERIAL_NUMBER,
        "x-api-key": DEVICE_API_KEY,
    }

    payload = {
        "user": user_identifier,
        "message": message,
        "type": notification_type,
    }

    try:
        response = requests.post(
            f"{SERVER_BASE_URL}/api/notifications/create",
            json=payload,
            headers=headers,
            timeout=10,
        )
        response.raise_for_status()
        print(f"[✅ NOTIFICATION SENT] '{message}' -> {user_identifier}")
    except requests.RequestException as e:
        print(f"[❌ NOTIFICATION FAILED] {e}")
