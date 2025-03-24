import os
import csv
import time
import requests
from datetime import datetime
from dotenv import load_dotenv
import spidev
import smbus
import RPi.GPIO as GPIO

# Load environment variables
load_dotenv()
SERVER_BASE_URL = os.getenv("SERVER_BASE_URL")
SERIAL_NUMBER = os.getenv("SERIAL_NUMBER")
DEVICE_API_KEY = os.getenv("DEVICE_API_KEY")

# Validate environment
if not SERVER_BASE_URL or not SERIAL_NUMBER or not DEVICE_API_KEY:
    raise EnvironmentError("[❌ CONFIG] Missing environment variables. Check .env setup.")

# Setup SPI and I2C
spi = spidev.SpiDev()
spi.open(0, 0)
spi.max_speed_hz = 500000
i2c_bus = smbus.SMBus(1)

# Pin mapping
DIGITAL_SENSOR_PINS = {
    "water_level": 17,
    "motion": 27,
    "algicide_level": 22,
    "chlorine_level": 23,
    "soda_level": 24,
    "pool_tank_level": 18,
}

# I2C sensor addresses
I2C_ADDRESS_UV = 0x38
I2C_ADDRESS_ORP = 0x39

# Safe range validation thresholds
SENSOR_THRESHOLDS = {
    "pH": {"min": 7.2, "max": 7.8},
    "chlorine": {"min": 1, "max": 3},
}


def initialize_sensors():
    """Initialize all digital GPIO sensors."""
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    for name, pin in DIGITAL_SENSOR_PINS.items():
        GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
        print(f"[✅ SENSOR INIT] {name} pin {pin} configured.")
    time.sleep(2)
    print("[✅ SENSOR INIT] All sensors initialized.\n")


def read_adc(channel):
    """Read analog value from ADC0834 on the specified channel."""
    if channel not in range(4):
        raise ValueError("ADC channel must be between 0 and 3.")
    try:
        adc = spi.xfer2([1, (8 + channel) << 4, 0])
        raw = ((adc[1] & 0x03) << 8) + adc[2]
        voltage = round((raw / 1023.0) * 3.3, 2)
        print(f"[🔍 ADC] Channel {channel} => {voltage} V")
        return voltage
    except Exception as e:
        print(f"[❌ ADC ERROR] Channel {channel}: {e}")
        return None


def read_i2c_sensor(address):
    """Read a value from an I2C sensor."""
    try:
        data = i2c_bus.read_word_data(address, 0x00)
        print(f"[🔍 I2C] Address {hex(address)} => {data}")
        return data
    except Exception as e:
        print(f"[❌ I2C ERROR] Failed to read from {hex(address)}: {e}")
        return None


def read_digital_sensor(sensor_type):
    """Read the state of a digital GPIO sensor."""
    pin = DIGITAL_SENSOR_PINS.get(sensor_type)
    if pin is None:
        print(f"[⚠️ WARNING] Unknown sensor: {sensor_type}")
        return None
    try:
        state = GPIO.input(pin)
        print(f"[🔍 DIGITAL] {sensor_type} (pin {pin}) => {'HIGH' if state else 'LOW'}")
        return state
    except Exception as e:
        print(f"[❌ DIGITAL ERROR] {sensor_type}: {e}")
        return None


def validate_sensor_reading(sensor_type, value):
    """Validate if a sensor reading falls within its configured thresholds."""
    thresholds = SENSOR_THRESHOLDS.get(sensor_type)
    if thresholds:
        if value is None:
            print(f"[❌ VALIDATION] No value for {sensor_type}.")
            return False
        if value < thresholds["min"]:
            print(f"[⚠️ VALIDATION] {sensor_type} too low: {value} < {thresholds['min']}")
            return False
        if value > thresholds["max"]:
            print(f"[⚠️ VALIDATION] {sensor_type} too high: {value} > {thresholds['max']}")
            return False
    return True


def log_sensor_data_locally(sensor_data, filename="sensor_log.csv"):
    """Append sensor data with timestamp to a local CSV log."""
    file_exists = os.path.isfile(filename)
    sensor_data["timestamp"] = datetime.now().isoformat()
    try:
        with open(filename, mode="a", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=["timestamp"] + list(sensor_data.keys()))
            if not file_exists:
                writer.writeheader()
            writer.writerow(sensor_data)
        print(f"[💾 CSV] Sensor data logged locally in '{filename}'")
    except Exception as e:
        print(f"[❌ CSV ERROR] Failed to write log: {e}")


def log_sensor_data(sensor_data):
    """Log sensor data both locally and remotely."""
    # Local CSV log
    log_sensor_data_locally(sensor_data)

    # Remote server log
    try:
        response = requests.post(
            f"{SERVER_BASE_URL}/api/devices/sensor-data",
            json={"sensorData": sensor_data},
            headers={
                "Content-Type": "application/json",
                "x-api-key": DEVICE_API_KEY,
                "x-serial-number": SERIAL_NUMBER,
            },
        )
        response.raise_for_status()
        print("[✅ SERVER] Sensor data sent to server.\n")
    except requests.RequestException as e:
        print(f"[❌ SERVER ERROR] Sensor data upload failed: {e}\n")


def fetch_sensor_readings():
    """Fetch and return current values of all connected sensors."""
    print("\n[📡 SENSOR READINGS]")
    data = {
        "pH": read_adc(0),
        "temperature": read_adc(1),
        "uv": read_i2c_sensor(I2C_ADDRESS_UV),
        "orp": read_i2c_sensor(I2C_ADDRESS_ORP),
        "waterLevel": read_digital_sensor("water_level"),
        "poolTankLevel": read_digital_sensor("pool_tank_level"),
    }
    print("[📦 DONE] All sensor readings collected.\n")
    return data
