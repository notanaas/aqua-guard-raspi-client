import os
import json
import requests
from datetime import datetime
from pathlib import Path
from modules.blockchain import log_to_blockchain
from modules.gpio_utils import initialize_gpio, cleanup_gpio
from modules.device_settings import fetch_user_and_device_settings
from modules.notifications import notify_server
from modules.relays import control_relay, sync_actuators_with_server
import csv

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

SERVER_BASE_URL = os.getenv("SERVER_BASE_URL")
SERIAL_NUMBER = os.getenv("SERIAL_NUMBER")
DEVICE_API_KEY = os.getenv("DEVICE_API_KEY")

if not SERVER_BASE_URL or not SERIAL_NUMBER or not DEVICE_API_KEY:
    raise ValueError("SERVER_BASE_URL, SERIAL_NUMBER, and DEVICE_API_KEY must be set in the environment variables.")

# Paths
LOG_PATH = Path("logs/actions_log.csv")

def log_to_csv(sensor_data, actions):
    """Log sensor data, relay actions, and device settings to a CSV file."""
    log_entry = {"timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), **sensor_data}
    for action in actions:
        log_entry[f"{action['actuator']}_command"] = action["command"]
        log_entry[f"{action['actuator']}_message"] = action["message"]

    try:
        with open(LOG_PATH, "a", newline="") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=log_entry.keys())
            if csvfile.tell() == 0:
                writer.writeheader()
            writer.writerow(log_entry)
        print(f"Action logged to CSV: {log_entry}")
    except Exception as e:
        print(f"Error logging to CSV: {e}")

def evaluate_rules(sensor_data, user_settings):
    actions = []

    # Safely extract settings with defaults
    pH_range = user_settings.get("preferred_pH_range", [7.2, 7.8])
    pool_info = user_settings.get("poolInfo", {})
    min_water = pool_info.get("minWaterLevel", 30)
    max_water = pool_info.get("maxWaterLevel", 70)
    desired_temp = pool_info.get("desiredTemperature", 28)

    # pH control logic
    if sensor_data["pH"] < pH_range[0]:
        actions.append({"actuator": "chlorine_pump", "command": "ON", "message": "pH low, activating chlorine pump."})
    elif sensor_data["pH"] > pH_range[1]:
        actions.append({"actuator": "chlorine_pump", "command": "OFF", "message": "pH high, deactivating chlorine pump."})

    # Water level control
    if sensor_data["waterLevel"] < min_water:
        actions.append({"actuator": "water_in", "command": "ON", "message": "Water level low, filling pool."})
    elif sensor_data["waterLevel"] > max_water:
        actions.append({"actuator": "water_out", "command": "ON", "message": "Water level high, draining pool."})

    # Temperature control
    if sensor_data["temperature"] < desired_temp:
        actions.append({"actuator": "pool_heater", "command": "ON", "message": "Temperature low, activating heater."})
    elif sensor_data["temperature"] > desired_temp + 2:
        actions.append({"actuator": "pool_heater", "command": "OFF", "message": "Temperature high, deactivating heater."})

    return actions

def execute_actions(actions):
    """Execute actions using API and log them to the blockchain and notify the server."""
    for action in actions:
        payload = {"actuatorType": action["actuator"], "command": action["command"]}
        headers = {
            "Content-Type": "application/json",
            "x-api-key": DEVICE_API_KEY,
            "x-serial-number": SERIAL_NUMBER,
        }
        try:
            response = requests.post(f"{SERVER_BASE_URL}/control-actuator", json=payload, headers=headers, timeout=10)
            response.raise_for_status()
            print(f"Actuator controlled: {action}")

            # Log to blockchain
            log_to_blockchain("actuator_action", action)

            # Send notification to the server
            notify_server(user_identifier=SERIAL_NUMBER,message=action["message"],notification_type="info" if action["command"] == "ON" else "warning",)
        except requests.RequestException as e:
            print(f"Failed to execute action for actuator {action['actuator']}: {e}")

def execute_actions(actions):
    """Execute actions using the control_relay function."""
    for action in actions:
        try:
            control_relay(action["actuator"], action["command"])
            notify_server(SERIAL_NUMBER, action["message"], "info")
        except Exception as e:
            print(f"Failed to execute action for actuator {action['actuator']}: {e}")


def main(sensor_data):
    """Main logic for evaluating sensor data and managing relays."""
    try:
        # Initialize GPIO
        initialize_gpio()

        # Fetch settings and actuator states from the server
        device_settings, user_settings = fetch_user_and_device_settings()
        if not device_settings or not user_settings:
            print("Failed to fetch settings. Exiting.")
            return

        # Sync actuators with the server
        sync_actuators_with_server()

        # Evaluate actions based on sensor data and settings
        actions = evaluate_rules(sensor_data, user_settings)

        # Execute actions and log them
        execute_actions(actions)
        log_to_csv(sensor_data, actions)

    except Exception as e:
        print(f"Error in main loop: {e}")
    finally:
        cleanup_gpio()

