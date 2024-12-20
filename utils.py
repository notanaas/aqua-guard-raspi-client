import os
import csv
import json

SETTINGS_FILE = "configs/settings.json"
LOG_FILE = "logs/sensor_log.csv"

def initialize_csv():
    """Initialize the CSV file for sensor data logging."""
    if not os.path.exists(LOG_FILE):
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        with open(LOG_FILE, mode='w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(["Timestamp", "Sensor", "Value"])

def rotate_log():
    """Rotate the log file if it exceeds a certain size."""
    if os.path.exists(LOG_FILE) and os.path.getsize(LOG_FILE) > 10 * 1024 * 1024:  # 10MB
        os.rename(LOG_FILE, f"{LOG_FILE}.old")
        initialize_csv()

def read_dynamic_settings():
    """Read settings from a JSON file."""
    try:
        with open(SETTINGS_FILE, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        print("Settings file not found. Using default settings.")
        return {
            "blockchain_url": "http://127.0.0.1:7545",
            "contract_address": "DEPLOYED_CONTRACT_ADDRESS",
            "contract_abi": "[]",
            "serial_number": "DEV-1234567890",
            "read_interval": 5,
            "gpio_pins": {
                "water_switch": 17,
                "motion_sensor": 27
            }
        }

def save_settings(settings):
    """Save settings to a JSON file."""
    try:
        with open(SETTINGS_FILE, 'w') as file:
            os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
            json.dump(settings, file, indent=4)
    except Exception as e:
        print(f"Error saving settings: {e}")
