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

# Global variable for token storage
ACCESS_TOKEN = None

# Hashing the API Key
def hash_api_key(api_key):
    return sha256(api_key.encode()).hexdigest()

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
        else:
            raise ValueError("Unsupported HTTP method.")

        response.raise_for_status()
        return response.json()
    except requests.HTTPError as e:
        if response.status_code == 401:
            print("Token expired. Re-authenticating...")
            login_device()
            return send_api_request(endpoint, method, data)
        else:
            print(f"API request failed: {e}")
            traceback.print_exc()
            return None

# Device login to obtain token
def login_device():
    global ACCESS_TOKEN
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
        ACCESS_TOKEN = data.get("token")
        if not ACCESS_TOKEN:
            raise ValueError("Token not returned from login.")
        print("Device login successful. Token obtained.")
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
    adc = spi.xfer2([1, (8 + channel) << 4, 0])
    value = ((adc[1] & 3) << 8) + adc[2]
    return value * (3.3 / 1023)

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
            response = send_api_request(f"{SERVER_BASE_URL}/api/devices/sensor-data", method="POST", data={"sensorData": sensor_data})
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
