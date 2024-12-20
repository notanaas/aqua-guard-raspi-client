import os
import json
import requests
import time
import traceback
import RPi.GPIO as GPIO
import spidev  # For ADC0834
import smbus  # For I2C communication
from dotenv import load_dotenv
from hashlib import sha256

# Load environment variables
load_dotenv()

# Environment variables
SERVER_BASE_URL = os.getenv('SERVER_BASE_URL')
SERIAL_NUMBER = os.getenv('SERIAL_NUMBER')
DEVICE_API_KEY = os.getenv('DEVICE_API_KEY')
BLOCKCHAIN_URL = os.getenv('BLOCKCHAIN_URL')
CONTRACT_ADDRESS = os.getenv('CONTRACT_ADDRESS')
CONTRACT_ABI_PATH = os.getenv('CONTRACT_ABI')

# GPIO Setup
GPIO.setmode(GPIO.BCM)

# Relay pins
RELAY_PINS = {
    "water_in": 23,
    "water_out": 16,
    "chlorine_pump": 18,
    "filter_head": 22
}
GPIO.setup(list(RELAY_PINS.values()), GPIO.OUT, initial=GPIO.LOW)

# Digital sensor pins
DIGITAL_SENSOR_PINS = {
    "water_level": 17,
    "motion": 27
}
GPIO.setup(list(DIGITAL_SENSOR_PINS.values()), GPIO.IN)

# ADC0834 Setup
spi = spidev.SpiDev()
spi.open(0, 0)
spi.max_speed_hz = 1000000

# I2C Setup for UV sensor
I2C_ADDRESS = 0x38
i2c_bus = smbus.SMBus(1)

# Global variables for token storage
ACCESS_TOKEN = None
REFRESH_TOKEN = None

# Hashing the API Key
def hash_api_key(api_key):
    return sha256(api_key.encode()).hexdigest()

# Save tokens locally
def save_tokens(access_token, refresh_token):
    with open("tokens.json", "w") as file:
        json.dump({"access_token": access_token, "refresh_token": refresh_token}, file)

# Load tokens from local file
def load_tokens():
    global ACCESS_TOKEN, REFRESH_TOKEN
    try:
        with open("tokens.json", "r") as file:
            tokens = json.load(file)
            ACCESS_TOKEN = tokens.get("access_token")
            REFRESH_TOKEN = tokens.get("refresh_token")
    except FileNotFoundError:
        ACCESS_TOKEN = None
        REFRESH_TOKEN = None

# Helper function for API requests
def send_api_request(endpoint, method="GET", data=None):
    global ACCESS_TOKEN
    url = f"{SERVER_BASE_URL}{endpoint}"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "X-API-Key": hash_api_key(DEVICE_API_KEY),
        "X-Serial-Number": SERIAL_NUMBER
    }
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
    except requests.HTTPError as e:
        if response.status_code == 401:
            print("Token expired. Attempting to refresh...")
            if refresh_access_token():
                return send_api_request(endpoint, method, data)  # Retry after refreshing token
        else:
            print(f"API request failed for endpoint '{endpoint}': {e}")
            traceback.print_exc()
            return None

# Refresh the access token using the refresh token
def refresh_access_token():
    global ACCESS_TOKEN, REFRESH_TOKEN
    try:
        response = requests.post(
            f"{SERVER_BASE_URL}/api/auth/refresh",
            json={"refreshToken": REFRESH_TOKEN},
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        data = response.json()
        ACCESS_TOKEN = data.get("accessToken")
        REFRESH_TOKEN = data.get("refreshToken")
        save_tokens(ACCESS_TOKEN, REFRESH_TOKEN)  # Save updated tokens
        print("Access token refreshed successfully.")
        return True
    except requests.RequestException as e:
        if e.response:
            print(f"Server response: {e.response.json()}")
        print(f"Failed to refresh token: {e}")
        traceback.print_exc()
        return False

# Device login to obtain initial tokens
def login_device():
    global ACCESS_TOKEN, REFRESH_TOKEN
    try:
        print(f"Attempting login with Serial Number: {SERIAL_NUMBER}, API Key: {DEVICE_API_KEY}")
        response = requests.post(
            f"{SERVER_BASE_URL}/api/auth/login-device",
            json={
                "serialNumber": SERIAL_NUMBER,
                "apiKey": DEVICE_API_KEY
            },
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        data = response.json()
        ACCESS_TOKEN = data.get("accessToken")
        REFRESH_TOKEN = data.get("refreshToken")
        if not ACCESS_TOKEN or not REFRESH_TOKEN:
            raise ValueError("Tokens not returned from login.")
        save_tokens(ACCESS_TOKEN, REFRESH_TOKEN)  # Save tokens locally
        print("Device login successful. Tokens obtained.")
    except requests.RequestException as e:
        if e.response:
            print(f"Server response: {e.response.json()}")
        print(f"Device login failed: {e}")
        traceback.print_exc()
        exit(1)

# Read sensors
def read_digital_sensor(sensor_type):
    pin = DIGITAL_SENSOR_PINS.get(sensor_type)
    if pin is None:
        raise ValueError(f"Invalid digital sensor type: {sensor_type}")
    return GPIO.input(pin)

def read_adc(channel):
    try:
        adc = spi.xfer2([1, (8 + channel) << 4, 0])
        value = ((adc[1] & 3) << 8) + adc[2]
        return round(value * (3.3 / 1023), 2)  # Convert to voltage and round to 2 decimals
    except Exception as e:
        print(f"Error reading ADC channel {channel}: {e}")
        return None

def read_uv_sensor():
    try:
        return i2c_bus.read_word_data(I2C_ADDRESS, 0x00)
    except Exception as e:
        print(f"Error reading UV sensor: {e}")
        return None

# Control relays
def control_relay(relay_name, state):
    pin = RELAY_PINS.get(relay_name)
    if pin is None:
        raise ValueError(f"Invalid relay name: {relay_name}")
    GPIO.output(pin, GPIO.HIGH if state == "ON" else GPIO.LOW)

# Main loop
def main_loop():
    print("Starting AquaGuard RPi Client...")
    load_tokens()
    if not ACCESS_TOKEN or not REFRESH_TOKEN:
        login_device()
    while True:
        try:
            # Read sensor data
            sensor_data = {
                "pH": read_adc(0),
                "temperature": read_adc(1),
                "pressure": read_adc(2),
                "current": read_adc(3),
                "waterLevel": read_digital_sensor("water_level"),
                "motion": read_digital_sensor("motion"),
                "uv": read_uv_sensor()
            }

            # Log sensor data to the server
            response = send_api_request("/api/devices/sensor-data", method="POST", data={"sensorData": sensor_data})
            if response:
                print("Sensor data logged successfully.")

            # Fetch and update actuator states
            actuator_states = send_api_request(f"/api/devices/{SERIAL_NUMBER}/actuator-states", method="GET")
            if actuator_states:
                for relay, state in actuator_states.items():
                    control_relay(relay, "ON" if state else "OFF")

            # Sleep before the next iteration
            time.sleep(10)

        except KeyboardInterrupt:
            print("Shutting down AquaGuard RPi Client...")
            break
        except Exception as e:
            print(f"Unexpected error: {e}")
            traceback.print_exc()
            time.sleep(10)

if __name__ == "__main__":
    try:
        main_loop()
    finally:
        GPIO.cleanup()
        spi.close()
