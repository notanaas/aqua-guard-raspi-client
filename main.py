import RPi.GPIO as GPIO
import smbus2
import time
import csv
import requests
import os
import json
import threading
from dotenv import load_dotenv
from websocket import WebSocketApp

# Load environment variables
load_dotenv()

# GPIO Pins
WATER_SWITCH_PIN = 26
MOTION_SENSOR_PIN = 27
RELAY_PINS = {
    "waterIn": 18,
    "waterOut": 23,
    "chlorinePump": 24,
    "filterHead": 25,
}

# I2C Configuration
I2C_BUS = 1
UV_SENSOR_ADDR = 0x38

# Backend API and WebSocket Configuration
API_BASE_URL = os.getenv("API_URL", "http://192.168.1.15:3001/api/devices")
WS_URL = "ws://192.168.1.15:3001"
SERIAL_NUMBER = os.getenv("SERIAL_NUMBER", "DEV-1234567890")
LOG_FILE = "sensor_log.csv"

# Setup GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setup(WATER_SWITCH_PIN, GPIO.IN)
GPIO.setup(MOTION_SENSOR_PIN, GPIO.IN)

for pin in RELAY_PINS.values():
    GPIO.setup(pin, GPIO.OUT)

# Initialize CSV Logging
def initialize_csv():
    try:
        with open(LOG_FILE, mode='a', newline='') as file:
            writer = csv.writer(file)
            if file.tell() == 0:
                writer.writerow(["Timestamp", "pH", "Temperature", "Pressure", "Current", "WaterLevel", "UV", "Motion", "Actions"])
    except Exception as e:
        print(f"Error initializing CSV: {e}")

# Log Rotation
def rotate_log():
    if os.path.getsize(LOG_FILE) > 10 * 1024 * 1024:  # 10MB
        os.rename(LOG_FILE, f"{LOG_FILE}.old")
        initialize_csv()

# Test GPIO Pins
def test_gpio():
    print("Testing GPIO Pins...")
    try:
        for pin in [WATER_SWITCH_PIN, MOTION_SENSOR_PIN]:
            print(f"Pin {pin} Input State: {GPIO.input(pin)}")

        for pin in RELAY_PINS.values():
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

# Mock Read ADC
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
    print("Sensor Readings:", data)
    return data

# Execute Actions
def execute_actions(actions):
    for action in actions:
        actuator = action.get("actuator")
        command = GPIO.HIGH if action.get("command") == "ON" else GPIO.LOW
        try:
            if actuator in RELAY_PINS:
                GPIO.output(RELAY_PINS[actuator], command)
                print(f"Executed action: {actuator}, Command: {'ON' if command == GPIO.HIGH else 'OFF'}")
        except Exception as e:
            print(f"Error executing action for {actuator}: {e}")

# Log Data
def log_data(sensor_data, actions):
    rotate_log()
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
            **sensor_data,
            "actuators": list(RELAY_PINS.keys()),  # Include actuators
        }
        print("Sending Payload:", payload)
        response = requests.post(f"{API_BASE_URL}/sensor-data", json=payload, headers=headers)
        response.raise_for_status()
        response_data = response.json()
        execute_actions(response_data.get("actions", []))
        log_data(sensor_data, response_data.get("actions", []))
    except requests.exceptions.RequestException as e:
        print(f"Request error: {e}")

# WebSocket Handlers
def on_message(ws, message):
    try:
        data = json.loads(message)
        print("Received WebSocket message:", data)
        if data["type"] == "command":
            actuator = data["actuator"]
            command = GPIO.HIGH if data["command"] == "ON" else GPIO.LOW
            if actuator in RELAY_PINS:
                GPIO.output(RELAY_PINS[actuator], command)
                print(f"Executed {actuator}: {'ON' if command == GPIO.HIGH else 'OFF'}")
                ws.send(json.dumps({
                    "type": "acknowledgment",
                    "serialNumber": SERIAL_NUMBER,
                    "actuator": actuator,
                    "status": "success",
                    "command": data["command"],
                }))
    except Exception as e:
        print(f"Error processing WebSocket message: {e}")

def on_error(ws, error):
    print("WebSocket Error:", error)

def on_close(ws, close_status_code, close_msg):
    print("WebSocket Closed:", close_status_code, close_msg)

def on_open(ws):
    ws.send(json.dumps({
        "type": "register",
        "serialNumber": SERIAL_NUMBER,
    }))

def start_websocket():
    while True:
        try:
            ws = WebSocketApp(
                WS_URL,
                on_message=on_message,
                on_error=on_error,
                on_close=on_close,
            )
            ws.on_open = on_open
            ws.run_forever()
        except Exception as e:
            retry_delay = random.uniform(5, 10)
            print(f"WebSocket error: {e}. Retrying in {retry_delay:.2f} seconds...")
            time.sleep(retry_delay)
# Main Loop
if __name__ == "__main__":
    try:
        initialize_csv()
        test_gpio()

        # Start WebSocket in a separate thread
        thread = threading.Thread(target=start_websocket)
        thread.daemon = True
        thread.start()

        while True:
            sensor_data = read_sensors()
            send_data(sensor_data)
            time.sleep(5)
    except KeyboardInterrupt:
        GPIO.cleanup()
    except Exception as e:
        print(f"An error occurred: {e}")
        GPIO.cleanup()
