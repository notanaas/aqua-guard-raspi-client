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
    raise ValueError("[❌ CONFIG ERROR] SERVER_BASE_URL, SERIAL_NUMBER, and DEVICE_API_KEY must be set.")

# GPIO pin configuration
RELAY_PINS = {
    "algicide_pump": 5,
    "chlorine_pump": 6,
    "soda_pump": 13,
    "pool_cover": 25,
    "water_in": 23,
    "water_out": 24,
    # Future pins below (uncomment when added physically):
    # "pool_tank_fill": 19,
    # "pool_tank_drain": 26,
    # "filter_head": 21,
    # "pool_heater": 20
}


def initialize_gpio():
    """Initialize GPIO relay pins."""
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    for relay_name, pin in RELAY_PINS.items():
        GPIO.setup(pin, GPIO.OUT, initial=GPIO.HIGH)
    print("[✅ GPIO] All relay pins initialized.")


def cleanup_gpio():
    """Clean up GPIO resources on exit."""
    GPIO.cleanup()
    print("[🧹 GPIO] GPIO cleanup complete.")


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
        print(f"[🌐 SYNC] Fetched actuator states: {actuators}")
        return actuators
    except requests.RequestException as e:
        print(f"[❌ ERROR] Failed to fetch actuator states: {e}")
        return []


def control_relay(relay_name, state):
    """Control a relay and propagate its state to blockchain and server."""
    pin = RELAY_PINS.get(relay_name)
    if pin is None:
        print(f"[⚠️ WARNING] Unknown relay '{relay_name}', skipping control.")
        return

    try:
        GPIO.output(pin, GPIO.LOW if state.upper() == "ON" else GPIO.HIGH)
        print(f"[⚙️ ACTUATOR] {relay_name.upper()} => {state.upper()}")

        log_to_blockchain("actuator_action", {
            "relay_name": relay_name,
            "state": state.upper()
        })

        update_actuator_state(relay_name, state)

    except Exception as e:
        print(f"[❌ GPIO ERROR] Failed to control '{relay_name}': {e}")


def update_actuator_state(relay_name, state):
    """Update the actuator state on the server."""
    url = f"{SERVER_BASE_URL}/api/devices/control-actuator"
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
        print(f"[✅ SERVER] {relay_name} state updated to {state.upper()} on server.")
    except requests.RequestException as e:
        print(f"[❌ SERVER ERROR] Failed to update '{relay_name}' state: {e}")


def sync_actuators_with_server():
    """Sync all actuators from the server to local GPIO state."""
    actuators = fetch_actuator_states()
    for actuator in actuators:
        control_relay(
            relay_name=actuator.get("type"),
            state="ON" if actuator.get("state") == "ON" else "OFF"
        )


def manage_pool_water_levels(sensor_data):
    """Manage pool water level based on sensor values."""
    water_level = sensor_data.get("waterLevel", 0)
    pool_tank_level = sensor_data.get("poolTankLevel", 0)

    print(f"\n[📊 WATER LEVEL MONITOR]")
    print(f"  - Pool water level: {water_level}")
    print(f"  - Pool tank level: {pool_tank_level}")

    if water_level < 50:
        print("[💧 ACTION] Low pool water level detected — starting water_in.")
        control_relay("water_in", "ON")
        control_relay("water_out", "OFF")
    elif pool_tank_level > 80:
        print("[🛠 ACTION] High tank level detected — draining pool via water_out.")
        control_relay("water_out", "ON")
        control_relay("water_in", "OFF")
    else:
        print("[👌 STATUS] Pool water level is stable.")
        control_relay("water_in", "OFF")
        control_relay("water_out", "OFF")


def manage_pool_tank(sensor_data):
    """Manage pool tank fill/drain operations."""
    tank_level = sensor_data.get("poolTankLevel", 0)

    print(f"\n[📊 POOL TANK MONITOR]")
    print(f"  - Tank level: {tank_level}")

    if tank_level < 20:
        print("[🚰 ACTION] Tank low — filling pool_tank_fill ON.")
        control_relay("pool_tank_fill", "ON")
        control_relay("pool_tank_drain", "OFF")
    elif tank_level > 80:
        print("[⚠️ ACTION] Tank high — draining pool_tank_drain ON.")
        control_relay("pool_tank_drain", "ON")
        control_relay("pool_tank_fill", "OFF")
    else:
        print("[👌 STATUS] Tank level is within acceptable range.")
        control_relay("pool_tank_fill", "OFF")
        control_relay("pool_tank_drain", "OFF")
