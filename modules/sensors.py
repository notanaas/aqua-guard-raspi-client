import spidev
import smbus
import RPi.GPIO as GPIO
import csv
import time
import requests
import os

# Environment variables for API
SERVER_BASE_URL = os.getenv("SERVER_BASE_URL")
SERIAL_NUMBER = os.getenv("SERIAL_NUMBER")
DEVICE_API_KEY = os.getenv("DEVICE_API_KEY")

# SPI and I2C setup
spi = spidev.SpiDev()
spi.open(0, 0)
spi.max_speed_hz = 500000

i2c_bus = smbus.SMBus(1)

# Sensor pin mapping
DIGITAL_SENSOR_PINS = {
    "water_level": 17,
    "motion": 27,
    "algicide_level": 22,
    "chlorine_level": 23,
    "soda_level": 24,
    "pool_tank_level": 18,
}

# I2C Addresses
I2C_ADDRESS_UV = 0x38
I2C_ADDRESS_ORP = 0x39

# Thresholds
SENSOR_THRESHOLDS = {
    "pH": {"min": 7.2, "max": 7.8},
    "chlorine": {"min": 1, "max": 3},
}

def initialize_sensors():
    """Initialize sensors."""
    print("Initializing sensors...")
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    for pin in DIGITAL_SENSOR_PINS.values():
        GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    time.sleep(2)  # Simulate initialization delay
    print("Sensors initialized.")

def read_adc(channel):
    """Read data from ADC0834."""
    if channel < 0 or channel > 3:
        raise ValueError("Channel must be between 0 and 3.")
    try:
        adc = spi.xfer2([1, (8 + channel) << 4, 0])
        raw_value = ((adc[1] & 0x03) << 8) + adc[2]
        voltage = (raw_value / 1023.0) * 3.3  # Convert to voltage
        return round(voltage, 2)
    except Exception as e:
        print(f"Error reading ADC channel {channel}: {e}")
        return None

def read_i2c_sensor(address):
    """Read data from I2C sensors."""
    try:
        return i2c_bus.read_word_data(address, 0x00)
    except Exception as e:
        print(f"Error reading I2C sensor at {hex(address)}: {e}")
        return None

def read_digital_sensor(sensor_type):
    """Read data from digital sensors."""
    pin = DIGITAL_SENSOR_PINS.get(sensor_type)
    if pin is None:
        raise ValueError(f"Invalid digital sensor type: {sensor_type}")
    try:
        return GPIO.input(pin)
    except Exception as e:
        print(f"Error reading digital sensor '{sensor_type}': {e}")
        return None

def validate_sensor_reading(sensor_type, value):
    """Validate sensor reading against thresholds."""
    thresholds = SENSOR_THRESHOLDS.get(sensor_type)
    if thresholds:
        if "min" in thresholds and value < thresholds["min"]:
            print(f"{sensor_type} reading too low: {value}")
            return False
        if "max" in thresholds and value > thresholds["max"]:
            print(f"{sensor_type} reading too high: {value}")
            return False
    return True


def log_sensor_data(sensor_data):
    """Log sensor data to the server and locally."""
    # Log locally
    log_sensor_data_locally(sensor_data)

    # Log remotely
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
        print("Sensor data logged successfully to the server.")
    except requests.RequestException as e:
        print(f"Failed to log sensor data to the server: {e}")

def fetch_sensor_readings():
    """Fetch readings from all sensors."""
    sensor_data = {
        "pH": read_adc(0),
        "temperature": read_adc(1),
        "uv": read_i2c_sensor(I2C_ADDRESS_UV),
        "orp": read_i2c_sensor(I2C_ADDRESS_ORP),
        "water_level": read_digital_sensor("water_level"),
    }
    return sensor_data
