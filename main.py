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
WATER_SWITCH_PIN = 17
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
SERIAL_NUMBER = os.getenv("SERIAL_NUMBER", "DEV-1234567890")  # Replace with actual serial number
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

# Read UV Sensor
def read_uv_sensor():
    try:
        bus = smbus2.SMBus(I2C_BUS)
        uv_data = bus.read_byte(UV_SENSOR_ADDR)
        return uv_data / 256.0  # Normalize
    except Exception as e:
        print(f"Error reading UV sensor: {e}")
        return 0

# Read ADC (Mock)
def read_adc(channel):
    try:
        return round((channel + 1) * 0.5, 2)  # Mock value
    except Exception as e:
        print(f"Error reading ADC channel {channel}: {e}")
        return 0

# Read Sensors
def read_sensors():
    return {
        "pH": read_adc(0),
        "temperature": read_adc(1),
        "pressure": read_adc(2),
        "current": read_adc(3),
        "waterLevel": GPIO.input(WATER_SWITCH_PIN),
        "uvIntensity": read_uv_sensor(),
        "motion": GPIO.input(MOTION_SENSOR_PIN),
    }

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
                sensor_data["uvIntensity"],
                sensor_data["motion"],
                action_summary,
            ])
    except Exception as e:
        print(f"Error logging data: {e}")

# Send Data to Server
def send_data(sensor_data):
    try:
        payload = {
            "serialNumber": SERIAL_NUMBER,
            "sensorData": sensor_data,
        }
        response = requests.post(f"{API_BASE_URL}/api/device/sensor-data", json=payload)
        response.raise_for_status()  # Raise error for bad status codes
        response_data = response.json()
        actions = response_data.get("actions", [])
        log_data(sensor_data, actions)
    except Exception as e:
        print(f"Error sending data to server: {e}")

# Cleanup
def cleanup():
    GPIO.cleanup()

# Main Loop
if __name__ == "__main__":
    try:
        initialize_csv()

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
