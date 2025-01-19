import time
import hashlib
import requests
from dotenv import load_dotenv
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

# Local blockchain storage
local_blockchain = []

def log_to_blockchain(event_type, data):
    """
    Log events to the local blockchain.

    Args:
        event_type (str): Type of event (e.g., "sensor_reading", "error").
        data (dict): Data to log in the blockchain.

    Returns:
        None
    """
    prev_hash = local_blockchain[-1]["hash"] if local_blockchain else "0"
    block = {
        "timestamp": time.time(),
        "event_type": event_type,
        "data": data,
        "previous_hash": prev_hash,
        "hash": hashlib.sha256(f"{str(data)}{prev_hash}".encode()).hexdigest(),
    }
    local_blockchain.append(block)
    print(f"Blockchain Log: {block}")

def sync_blockchain():
    """
    Sync the local blockchain with the server.

    Returns:
        None
    """
    headers = {
        "x-api-key": DEVICE_API_KEY,
        "x-serial-number": SERIAL_NUMBER,
        "Content-Type": "application/json",
    }
    if not local_blockchain:
        print("No new blocks to sync with the server.")
        return

    try:
        response = requests.post(
            f"{SERVER_BASE_URL}/api/devices/blockchain/sync",
            json={"blockchain": local_blockchain},
            headers=headers,
            timeout=10,
        )
        response.raise_for_status()
        local_blockchain.clear()  # Clear local blockchain after successful sync
        print("Blockchain synced successfully.")
    except requests.RequestException as e:
        print(f"Failed to sync blockchain: {e}")
