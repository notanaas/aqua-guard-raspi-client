import os
import json
import requests
import time
import traceback
import RPi.GPIO as GPIO
import spidev  # For ADC0834
import smbus  # For I2C communication
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Environment variables
SERVER_BASE_URL = os.getenv("SERVER_BASE_URL")
SERIAL_NUMBER = os.getenv("SERIAL_NUMBER")
DEVICE_API_KEY = os.getenv("DEVICE_API_KEY")

# GPIO Setup
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

# Relay pins
RELAY_PINS = {
    "water_in": 23,
    "water_out": 16,
    "chlorine_pump": 18,
    "filter_head": 22,
}
GPIO.setup(list(RELAY_PINS.values()), GPIO.OUT, initial=GPIO.LOW)

# Digital sensor pins
DIGITAL_SENSOR_PINS = {
    "water_level": 17,
    "motion": 27,
}
GPIO.setup(list(DIGITAL_SENSOR_PINS.values()), GPIO.IN)

# ADC0834 Setup
spi = spidev.SpiDev()
spi.open(0, 0)
spi.max_speed_hz = 1000000

# I2C Setup for UV sensor
I2C_ADDRESS = 0x38
i2c_bus = smbus.SMBus(1)

def send_api_request(endpoint, method="GET", data=None):
    url = f"{SERVER_BASE_URL}{endpoint}"
    headers = {
        "Content-Type": "application/json",
        "x-api-key": DEVICE_API_KEY,
        "x-serial-number": SERIAL_NUMBER,
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
    except requests.RequestException as e:
        print(f"API request failed for {endpoint}: {e}")
        traceback.print_exc()
        return None

# Read sensors
def read_digital_sensor(sensor_type):
    pin = DIGITAL_SENSOR_PINS.get(sensor_type)
    if pin is None:
        raise ValueError(f"Invalid digital sensor type: {sensor_type}")
    try:
        return GPIO.input(pin)
    except Exception as e:
        print(f"Error reading digital sensor {sensor_type}: {e}")
        return None

def read_adc(channel):
    try:
        adc = spi.xfer2([1, (8 + channel) << 4, 0])
        value = ((adc[1] & 3) << 8) + adc[2]
        return round(value * (3.3 / 1023), 2)  # Convert to voltage and round to 2 decimals
    except Exception as e:
        print(f"Error reading ADC channel {channel}: {e}")
        return None

def read_uv_sensor(retries=3):
    for attempt in range(retries):
        try:
            return i2c_bus.read_word_data(I2C_ADDRESS, 0x00)
        except Exception as e:
            print(f"Error reading UV sensor on attempt {attempt + 1}/{retries}: {e}")
            time.sleep(1)  # Retry delay
    print("Failed to read UV sensor after multiple attempts.")
    return None

# Control relays
def control_relay(relay_name, state):
    pin = RELAY_PINS.get(relay_name)
    if pin is None:
        print(f"Invalid relay name: {relay_name}")
        return
    try:
        GPIO.output(pin, GPIO.HIGH if state == "ON" else GPIO.LOW)
        print(f"Relay '{relay_name}' set to {state}")
    except Exception as e:
        print(f"Error controlling relay {relay_name}: {e}")

# Main loop
def main_loop():
    print("Starting AquaGuard RPi Client...")
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
                "uv": read_uv_sensor(),
            }
            print(f"Sensor data: {sensor_data}")

            # Log all sensor data in one POST request
            response = send_api_request(
                "/api/devices/sensor-data", 
                method="POST", 
                data={"sensorData": sensor_data}
            )
            if response:
                print("Sensor data logged successfully.")

            # Fetch and update actuator states
            actuator_states = send_api_request(f"/api/devices/{SERIAL_NUMBER}/actuator-states", method="GET")
            if actuator_states and isinstance(actuator_states, list):
                for actuator in actuator_states:
                    if isinstance(actuator, dict) and 'type' in actuator and 'state' in actuator:
                        control_relay(actuator['type'], "ON" if actuator['state'] else "OFF")
                    else:
                        print(f"Invalid actuator data: {actuator}")
            else:
                print("No valid actuator states received.")

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
