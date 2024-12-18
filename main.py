import RPi.GPIO as GPIO
import smbus2
import time
import csv
import requests
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# GPIO Pins
WATER_SWITCH_PIN = 26
MOTION_SENSOR_PIN = 27
RELAY_WATER_IN_PIN = 18
RELAY_WATER_OUT_PIN = 23
RELAY_CHLORINE_PUMP_PIN = 24
RELAY_FILTER_HEAD_PIN = 25

# I2C Configuration
I2C_BUS = 1
UV_SENSOR_ADDR = 0x38

# Backend API Configuration
API_BASE_URL = os.getenv("API_URL", "http://192.168.1.15:3001/api/devices")
SERIAL_NUMBER = os.getenv("SERIAL_NUMBER", "DEV-1234567890")
LOG_FILE = "sensor_log.csv"

# Setup GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setup(WATER_SWITCH_PIN, GPIO.IN)
GPIO.setup(MOTION_SENSOR_PIN, GPIO.IN)
GPIO.setup(RELAY_WATER_IN_PIN, GPIO.OUT)
GPIO.setup(RELAY_WATER_OUT_PIN, GPIO.OUT)
GPIO.setup(RELAY_CHLORINE_PUMP_PIN, GPIO.OUT)
GPIO.setup(RELAY_FILTER_HEAD_PIN, GPIO.OUT)

# Initialize CSV Logging
def initialize_csv():
    try:
        with open(LOG_FILE, mode='a', newline='') as file:
            writer = csv.writer(file)
            if file.tell() == 0:
                writer.writerow(["Timestamp", "pH", "Temperature", "Pressure", "Current", "WaterLevel", "UV", "Motion", "Actions"])
    except Exception as e:
        print(f"Error initializing CSV: {e}")

# Test GPIO Pins
def test_gpio():
    print("Testing GPIO Pins...")
    try:
        for pin in [WATER_SWITCH_PIN, MOTION_SENSOR_PIN]:
            GPIO.setup(pin, GPIO.IN)
            print(f"Pin {pin} Input State: {GPIO.input(pin)}")

        for pin in [RELAY_WATER_IN_PIN, RELAY_WATER_OUT_PIN, RELAY_CHLORINE_PUMP_PIN, RELAY_FILTER_HEAD_PIN]:
            GPIO.setup(pin, GPIO.OUT)
            GPIO.output(pin, GPIO.HIGH)
            time.sleep(0.1)
            GPIO.output(pin, GPIO.LOW)
            print(f"Pin {pin} toggled successfully")
    except Exception as e:
        print(f"Error testing GPIO: {e}")

# Read UV Sensor
def read_uv_sensor():
    try:
        bus = smbus2.SMBus(I2C_BUS)
        uv_data = bus.read_byte(UV_SENSOR_ADDR)
        return uv_data / 256.0
    except Exception as e:
        print(f"Error reading UV sensor: {e}")
        return 0

# Read ADC (Mock)
def read_adc(channel):
    try:
        value = channel * 0.5  # Replace with actual ADC read logic
        print(f"ADC Channel {channel}: {value}")
        return value
    except Exception as e:
        print(f"Error reading ADC channel {channel}: {e}")
        return 0

# Read Sensors
def read_sensors():
    data = {
        "pH": read_adc(0),
        "temperature": read_adc(1),
        "pressure": read_adc(2),
        "current": read_adc(3),
        "waterLevel": GPIO.input(WATER_SWITCH_PIN),
        "uv": read_uv_sensor(),
        "motion": GPIO.input(MOTION_SENSOR_PIN),
    }
    print("Sensor Readings:", data)  # Debugging output
    return data

# Execute Actions
# Execute Actions
def execute_actions(actions):
    for action in actions:
        actuator = action.get("actuator")
        command = GPIO.HIGH if action.get("command") == "ON" else GPIO.LOW
        try:
            if actuator == "waterIn":
                GPIO.output(RELAY_WATER_IN_PIN, command)
            elif actuator == "waterOut":
                GPIO.output(RELAY_WATER_OUT_PIN, command)
            elif actuator == "chlorinePump":
                GPIO.output(RELAY_CHLORINE_PUMP_PIN, command)
            elif actuator == "filterHead":
                GPIO.output(RELAY_FILTER_HEAD_PIN, command)
            print(f"Executed action: {actuator}, Command: {command}")
            print(f"Confirmation: {actuator} successfully set to {'ON' if command == GPIO.HIGH else 'OFF'}")
        except Exception as e:
            print(f"Error executing action for {actuator}: {e}")


# Log Data
def log_data(sensor_data, actions):
    try:
        with open(LOG_FILE, mode='a', newline='') as file:
            writer = csv.writer(file)
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            action_summary = "|".join([f"{a['actuator']}:{a['command']}" for a in actions])
            writer.writerow([
                timestamp,
                sensor_data["pH"],
                sensor_data["temperature"],
                sensor_data["pressure"],
                sensor_data["current"],
                sensor_data["waterLevel"],
                sensor_data["uv"],
                sensor_data["motion"],
                action_summary,
            ])
    except Exception as e:
        print(f"Error logging data: {e}")

# Send Data to Server
def send_data(sensor_data):
    try:
        headers = {
            "serialNumber": SERIAL_NUMBER,
            "Content-Type": "application/json",
        }
        payload = {
            "pH": sensor_data["pH"],
            "temperature": sensor_data["temperature"],
            "pressure": sensor_data["pressure"],
            "current": sensor_data["current"],
            "waterLevel": sensor_data["waterLevel"],
            "uv": sensor_data["uv"],
            "motion": sensor_data["motion"],
        }
        print("Sending Payload:", payload)  # Debugging payload
        response = requests.post(f"{API_BASE_URL}/sensor-data", json=payload, headers=headers)
        response.raise_for_status()
        response_data = response.json()
        actions = response_data.get("actions", [])
        execute_actions(actions)
        log_data(sensor_data, actions)
    except requests.exceptions.HTTPError as e:
        print(f"HTTP Error: {e.response.status_code} - {e.response.text}")
    except requests.exceptions.RequestException as e:
        print(f"Request error: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")
def send_command_confirmation(actuator, command):
    try:
        payload = {
            "actuator": actuator,
            "status": "success",
            "command": "ON" if command == GPIO.HIGH else "OFF"
        }
        response = requests.post(f"{API_BASE_URL}/command-confirmation", json=payload)
        response.raise_for_status()
        print(f"Command confirmation sent for {actuator}: {payload}")
    except Exception as e:
        print(f"Error sending command confirmation for {actuator}: {e}")

# Include this in the loop of `execute_actions`
        send_command_confirmation(actuator, command)

# Cleanup
def cleanup():
    GPIO.cleanup()

# Main Loop
if __name__ == "__main__":
    try:
        initialize_csv()
        test_gpio()  # Test GPIO pins
        while True:
            sensor_data = read_sensors()
            print("Sensor Data:", sensor_data)
            send_data(sensor_data)
            time.sleep(5)
    except KeyboardInterrupt:
        cleanup()
    except Exception as e:
        print(f"An error occurred: {e}")
        cleanup()
