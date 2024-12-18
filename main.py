import RPi.GPIO as GPIO
import smbus2
import time
import csv
import requests
from config import PRIMARY_SERVER, DEVICE_SERIAL, DEVICE_PASSWORD, LOG_FILE
from kbs import evaluate_rules, send_actions_to_actuators

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
    # Replace with real ADC SPI code if needed
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
            writer.writerow([timestamp, sensor_data["pH"], sensor_data["temperature"], sensor_data["pressure"], sensor_data["current"], sensor_data["waterLevel"], sensor_data["uvIntensity"], sensor_data["motion"], action_summary])
    except Exception as e:
        print(f"Error logging data: {e}")

# Send Data to Server
def send_data(sensor_data):
    try:
        response = requests.post(
            f"{PRIMARY_SERVER}/api/devices/sensor-data",
            json=sensor_data,
            headers={"Authorization": f"Bearer {DEVICE_SERIAL}"}
        )
        response_data = response.json()
        actions = response_data.get("actions", [])
        send_actions_to_actuators(actions)
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
