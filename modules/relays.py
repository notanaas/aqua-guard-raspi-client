import os
import requests
import RPi.GPIO as GPIO
from modules.blockchain import log_to_blockchain
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Environment variables
SERVER_BASE_URL = os.getenv("SERVER_BASE_URL")
SERIAL_NUMBER = os.getenv("SERIAL_NUMBER")
DEVICE_API_KEY = os.getenv("DEVICE_API_KEY")

if not SERVER_BASE_URL or not SERIAL_NUMBER or not DEVICE_API_KEY:
    raise ValueError("SERVER_BASE_URL, SERIAL_NUMBER, and DEVICE_API_KEY must be set in the environment variables.")

# GPIO setup
RELAY_PINS = {
    "algicide_pump": 5,
    "chlorine_pump": 6,
    "soda_pump": 13,
    "pool_cover": 25,
    "water_in": 23,
    "water_out": 24,
    "pool_tank_fill": 19,
    "pool_tank_drain": 26,
}

def initialize_gpio():
    """Initialize GPIO pins."""
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    for pin in RELAY_PINS.values():
        GPIO.setup(pin, GPIO.OUT, initial=GPIO.HIGH)  # Set initial state to OFF
    print("GPIO initialized.")

def cleanup_gpio():
    """Clean up GPIO resources."""
    GPIO.cleanup()
    print("GPIO cleaned up.")

def fetch_actuator_states():
    """Fetch actuator states from the server."""
    url = f"{SERVER_BASE_URL}/api/devices/{SERIAL_NUMBER}/actuator-states"
    headers = {
        "Content-Type": "application/json",
        "x-api-key": DEVICE_API_KEY,
        "x-serial-number": SERIAL_NUMBER,
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        actuators = response.json().get("actuators", [])
        print(f"Fetched actuator states: {actuators}")
        return actuators
    except requests.RequestException as e:
        print(f"Failed to fetch actuator states: {e}")
        return []

def control_relay(relay_name, state):
    """
    Control relay state and log changes to blockchain and server.

    Parameters:
        relay_name (str): The name of the relay/actuator to control.
        state (str): The desired state ("ON" or "OFF").
    """
    pin = RELAY_PINS.get(relay_name)
    if pin is None:
        print(f"Invalid relay name: {relay_name}")
        return

    # Update relay locally
    try:
        GPIO.output(pin, GPIO.LOW if state.upper() == "ON" else GPIO.HIGH)
        print(f"Relay '{relay_name}' set to {state}")

        # Log the action to blockchain
        log_to_blockchain("actuator_action", {"relay_name": relay_name, "state": state})

        # Update actuator state via API
        update_actuator_state(relay_name, state)
    except Exception as e:
        print(f"Error controlling relay '{relay_name}': {e}")

def update_actuator_state(relay_name, state):
    """
    Update the actuator state on the server.

    Parameters:
        relay_name (str): The name of the relay/actuator.
        state (str): The state ("ON" or "OFF").
    """
    url = f"{SERVER_BASE_URL}/devices/{SERIAL_NUMBER}/control-actuator"
    headers = {
        "Content-Type": "application/json",
        "x-api-key": DEVICE_API_KEY,
        "x-serial-number": SERIAL_NUMBER,
    }
    payload = {
        "actuatorType": relay_name,
        "command": state.upper(),
    }
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        print(f"Actuator state for '{relay_name}' updated successfully on the server.")
    except requests.RequestException as e:
        print(f"Failed to update actuator state for '{relay_name}': {e}")


def sync_actuators_with_server():
    """Sync local relay states with the server."""
    actuators = fetch_actuator_states()
    for actuator in actuators:
        relay_name = actuator["type"]
        state = "ON" if actuator["state"] == "ON" else "OFF"
        control_relay(relay_name, state)

def manage_pool_water_levels(sensor_data):
    """Control water in and out relays based on pool water level."""
    if sensor_data["waterLevel"] < 50:  # Example threshold for low water level
        print("Water level is low, filling water into the pool...")
        control_relay("water_in", "ON")
        control_relay("water_out", "OFF")
    elif sensor_data["poolTankLevel"] > 80:  # Example threshold for high tank level
        print("Draining water from the pool...")
        control_relay("water_out", "ON")
        control_relay("water_in", "OFF")
    else:
        print("Water level is stable.")
        control_relay("water_in", "OFF")
        control_relay("water_out", "OFF")

def manage_pool_tank(sensor_data):
    """Control pool tank filling or draining."""
    if sensor_data["poolTankLevel"] < 20:  # Example threshold for low tank level
        print("Pool tank level is low, filling the tank...")
        control_relay("pool_tank_fill", "ON")
        control_relay("pool_tank_drain", "OFF")
    elif sensor_data["poolTankLevel"] > 80:  # Example threshold for high tank level
        print("Draining excess water from the tank...")
        control_relay("pool_tank_drain", "ON")
        control_relay("pool_tank_fill", "OFF")
    else:
        print("Pool tank level is stable.")
        control_relay("pool_tank_fill", "OFF")
        control_relay("pool_tank_drain", "OFF")
