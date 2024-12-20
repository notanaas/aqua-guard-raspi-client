import os
import json
import csv
import subprocess

SETTINGS_FILE = "configs/settings.json"
LOG_FILE = "logs/sensor_log.csv"

def get_device_serial_number():
    """
    Fetches the Raspberry Pi's unique hardware serial number.
    """
    try:
        serial = None
        with open('/proc/cpuinfo', 'r') as file:
            for line in file:
                if line.startswith('Serial'):
                    serial = line.strip().split(":")[1].strip()
        if not serial:
            raise ValueError("Serial number not found.")
        return serial
    except Exception as e:
        print(f"Error retrieving device serial number: {e}")
        return "UNKNOWN_SERIAL"

def read_dynamic_settings():
    """
    Reads the settings from the local JSON file. If the serial number is not present,
    fetches it dynamically and updates the settings file.
    """
    try:
        with open(SETTINGS_FILE, 'r') as file:
            settings = json.load(file)
        
        # Check and update the serial number dynamically
        if not settings.get("serial_number") or settings["serial_number"] == "UNKNOWN_SERIAL":
            settings["serial_number"] = get_device_serial_number()
            save_settings(settings)
        
        return settings
    except FileNotFoundError:
        print("Settings file not found. Generating default settings with dynamic serial number.")
        default_settings = {
            "blockchain_url": "http://127.0.0.1:7545",
            "contract_address": "DEPLOYED_CONTRACT_ADDRESS",
            "contract_abi": "[]",
            "serial_number": get_device_serial_number(),
            "read_interval": 5,
            "gpio_pins": {
                "water_switch": 17,
                "motion_sensor": 27
            }
        }
        save_settings(default_settings)
        return default_settings

def save_settings(settings):
    """
    Saves the settings to the local JSON file.
    """
    try:
        os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
        with open(SETTINGS_FILE, 'w') as file:
            json.dump(settings, file, indent=4)
    except Exception as e:
        print(f"Error saving settings: {e}")

def initialize_csv():
    """
    Initializes the sensor log CSV file.
    """
    try:
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        if not os.path.exists(LOG_FILE):
            with open(LOG_FILE, mode='w', newline='') as file:
                writer = csv.writer(file)
                writer.writerow(["Timestamp", "Sensor", "Value"])
    except Exception as e:
        print(f"Error initializing CSV: {e}")
