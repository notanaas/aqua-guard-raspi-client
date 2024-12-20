import os
import json
import requests
import time
import traceback
from web3 import Web3
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Environment variables
BLOCKCHAIN_URL = os.getenv('BLOCKCHAIN_URL')
CONTRACT_ADDRESS = os.getenv('CONTRACT_ADDRESS')
CONTRACT_ABI_PATH = os.getenv('CONTRACT_ABI')
SERIAL_NUMBER = os.getenv('SERIAL_NUMBER')
SERVER_BASE_URL = os.getenv('SERVER_BASE_URL')

# Initialize Web3
try:
    with open(CONTRACT_ABI_PATH, 'r') as abi_file:
        contract_abi = json.load(abi_file)['abi']

    web3 = Web3(Web3.HTTPProvider(BLOCKCHAIN_URL))
    if not web3.isConnected():
        raise ConnectionError("Failed to connect to blockchain.")

    contract = web3.eth.contract(address=Web3.toChecksumAddress(CONTRACT_ADDRESS), abi=contract_abi)
    print("Blockchain client initialized successfully.")
except Exception as e:
    print(f"Error initializing blockchain client: {e}")
    traceback.print_exc()
    exit(1)

# Helper function for server API interaction
def send_api_request(endpoint, method="GET", data=None):
    url = f"{SERVER_BASE_URL}{endpoint}"
    headers = {"Content-Type": "application/json"}
    try:
        if method == "GET":
            response = requests.get(url, headers=headers)
        elif method == "POST":
            response = requests.post(url, json=data, headers=headers)
        elif method == "PATCH":
            response = requests.patch(url, json=data, headers=headers)
        else:
            raise ValueError("Unsupported HTTP method.")
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"API request failed: {e}")
        traceback.print_exc()
        return None

# Log sensor data to blockchain and server
def log_sensor_data(sensor_data):
    try:
        # Log to blockchain
        tx_hash = contract.functions.logSensorData(SERIAL_NUMBER, json.dumps(sensor_data)).transact({'from': web3.eth.accounts[0]})
        web3.eth.wait_for_transaction_receipt(tx_hash)
        print(f"Sensor data logged to blockchain: {tx_hash.hex()}")

        # Log to server
        response = send_api_request("/api/devices/sensor-data", method="POST", data={"serialNumber": SERIAL_NUMBER, "sensorData": sensor_data})
        if response:
            print("Sensor data logged to server.")
    except Exception as e:
        print(f"Error logging sensor data: {e}")
        traceback.print_exc()

# Fetch actuator states
def fetch_actuator_states():
    try:
        response = send_api_request(f"/api/devices/{SERIAL_NUMBER}/actuator-states", method="GET")
        if response:
            print(f"Actuator states: {response}")
            return response
    except Exception as e:
        print(f"Error fetching actuator states: {e}")
        traceback.print_exc()
    return None

# Update actuator state
def update_actuator_state(actuator, state):
    try:
        response = send_api_request(
            f"/api/devices/{SERIAL_NUMBER}/control-actuator",
            method="POST",
            data={"actuator": actuator, "command": "ON" if state else "OFF"}
        )
        if response:
            print(f"Actuator {actuator} updated successfully.")
    except Exception as e:
        print(f"Error updating actuator state: {e}")
        traceback.print_exc()

# Simulate reading sensors (replace with actual hardware code)
def read_sensor_data():
    try:
        return {
            "pH": 7.2,  # Replace with actual pH sensor reading
            "temperature": 28.5,  # Replace with actual temperature sensor reading
            "pressure": 1.2,  # Replace with actual pressure sensor reading
            "current": 0.8,  # Replace with actual current sensor reading
            "waterLevel": 0.9,  # Replace with actual water level sensor reading
            "uv": 0.3,  # Replace with actual UV sensor reading
            "motion": 1  # Replace with actual motion sensor reading
        }
    except Exception as e:
        print(f"Error reading sensor data: {e}")
        traceback.print_exc()
        return {}

def main_loop():
    """
    Main loop for reading sensor data, logging to the blockchain and server,
    and handling actuator states.
    """
    print("Starting AquaGuard RPi Client...")
    while True:
        try:
            # Read sensor data
            sensor_data = read_sensor_data()
            print(f"Sensor Data: {sensor_data}")

            # Log sensor data
            log_sensor_data(sensor_data)

            # Fetch and update actuator states
            actuator_states = fetch_actuator_states()
            if actuator_states:
                for actuator, state in actuator_states.items():
                    print(f"Setting {actuator} to {state}")
                    update_actuator_state(actuator, state)

            # Sleep before next iteration
            time.sleep(10)

        except KeyboardInterrupt:
            print("Shutting down AquaGuard RPi Client...")
            break
        except Exception as e:
            print(f"Unexpected error: {e}")
            traceback.print_exc()
            time.sleep(10)

if __name__ == "__main__":
    main_loop()
