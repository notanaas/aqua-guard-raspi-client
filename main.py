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

if not SERVER_BASE_URL or not SERIAL_NUMBER or not DEVICE_API_KEY:
    raise ValueError("SERVER_BASE_URL, SERIAL_NUMBER, and DEVICE_API_KEY must be set in the environment variables.")

# GPIO Setup
RELAY_PINS = {
    "water_in": 23,
    "water_out": 16,
    "chlorine_pump": 18,
    "filter_head": 22,
    "pool_cover": 25,
}
DIGITAL_SENSOR_PINS = {
    "water_level": 17,
    "motion": 27,
}

# ADC0834 Setup
spi = spidev.SpiDev()
spi.open(0, 0)
spi.max_speed_hz = 500000
spi.mode = 0

# I2C Setup for UV sensor
I2C_ADDRESS = 0x38
i2c_bus = smbus.SMBus(1)

def initialize_gpio():
    """Initialize GPIO pins."""
    GPIO.cleanup()  # Reset all GPIO pins
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)

    # Set up relay pins as outputs
    for pin in RELAY_PINS.values():
        GPIO.setup(pin, GPIO.OUT, initial=GPIO.LOW)

    # Set up digital sensor pins as inputs with pull-down resistors
    for pin in DIGITAL_SENSOR_PINS.values():
        GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

    print("GPIO initialization complete.")

def validate_gpio():
    """Validate GPIO connections."""
    print("Validating GPIO connections...")

    for relay_name, pin in RELAY_PINS.items():
        GPIO.setup(pin, GPIO.OUT)
        GPIO.output(pin, GPIO.HIGH)
        print(f"[Relay Test] {relay_name}: Pin {pin} set to HIGH.")
        time.sleep(0.5)
        GPIO.output(pin, GPIO.LOW)
        print(f"[Relay Test] {relay_name}: Pin {pin} set to LOW.")

    for sensor_name, pin in DIGITAL_SENSOR_PINS.items():
        GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
        state = GPIO.input(pin)
        print(f"[Sensor Test] {sensor_name}: Pin {pin} state is {'HIGH' if state else 'LOW'}.")

    print("GPIO validation complete.")

def send_api_request(endpoint, method="GET", data=None):
    """Send HTTP requests to the server."""
    url = f"{SERVER_BASE_URL}{endpoint}"
    headers = {
        "Content-Type": "application/json",
        "x-api-key": DEVICE_API_KEY,
        "x-serial-number": SERIAL_NUMBER,
    }
    try:
        if method.upper() == "GET":
            response = requests.get(url, headers=headers, timeout=10)
        elif method.upper() == "POST":
            response = requests.post(url, json=data, headers=headers, timeout=10)
        else:
            raise ValueError("Unsupported HTTP method.")
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"API request failed: {e}")
        return None

def read_digital_sensor(sensor_type):
    """Read data from a digital sensor."""
    pin = DIGITAL_SENSOR_PINS.get(sensor_type)
    if pin is None:
        raise ValueError(f"Invalid digital sensor type: {sensor_type}")
    try:
        state = GPIO.input(pin)
        print(f"Digital sensor '{sensor_type}' state: {'HIGH' if state else 'LOW'}")
        return state
    except Exception as e:
        print(f"Error reading digital sensor '{sensor_type}': {e}")
        return None

def read_adc(channel):
    """Read data from ADC0834 channel."""
    if channel < 0 or channel > 3:
        raise ValueError("Channel must be between 0 and 3.")
    try:
        adc = spi.xfer2([1, (8 + channel) << 4, 0])
        raw_value = ((adc[1] & 0x03) << 8) + adc[2]  # Combine the 10-bit result
        voltage = (raw_value / 1023.0) * 3.3  # Convert to voltage (3.3V reference)
        print(f"ADC Channel {channel} Value: {raw_value}, Voltage: {voltage:.2f}V")
        return round(voltage, 2)
    except Exception as e:
        print(f"Error reading ADC channel {channel}: {e}")
        return None

def read_uv_sensor(retries=3):
    """Read data from the UV sensor."""
    for attempt in range(retries):
        try:
            uv_data = i2c_bus.read_word_data(I2C_ADDRESS, 0x00)
            print(f"UV Sensor Data: {uv_data}")
            return uv_data
        except Exception as e:
            print(f"Error reading UV sensor on attempt {attempt + 1}/{retries}: {e}")
            time.sleep(1)
    print("Failed to read UV sensor after multiple attempts.")
    return None

def control_relay(relay_name, state):
    """Control relay states."""
    pin = RELAY_PINS.get(relay_name)
    if pin is None:
        print(f"Invalid relay name: {relay_name}")
        return
    try:
        if relay_name == "pool_cover":
            if state.upper() == "OPEN":
                GPIO.output(pin, GPIO.LOW)
                print(f"Relay '{relay_name}' is OPEN")
            elif state.upper() == "CLOSE":
                GPIO.output(pin, GPIO.HIGH)
                print(f"Relay '{relay_name}' is CLOSED")
        else:
            GPIO.output(pin, GPIO.LOW if state.upper() == "ON" else GPIO.HIGH)
            print(f"Relay '{relay_name}' set to {state}")
    except Exception as e:
        print(f"Error controlling relay '{relay_name}': {e}")

def log_sensor_data(sensor_data):
    """Send sensor data to the server."""
    response = send_api_request(
        "/api/devices/sensor-data",
        method="POST",
        data={"sensorData": sensor_data}
    )
    if response:
        print("Sensor data logged successfully.")
    else:
        print("Failed to log sensor data.")

def fetch_and_update_actuators():
    """Fetch actuator states and update relays."""
    actuator_states = send_api_request(f"/api/devices/{SERIAL_NUMBER}/actuator-states", method="GET")
    if actuator_states and 'actuators' in actuator_states and isinstance(actuator_states['actuators'], list):
        for actuator in actuator_states['actuators']:
            if 'type' in actuator and 'state' in actuator:
                control_relay(actuator['type'], actuator['state'])
    else:
        print("No valid actuator states received.")

def main_loop():
    """Main loop for reading sensors, logging data, and controlling relays."""
    print("Starting AquaGuard RPi Client...")
    initialize_gpio()
    validate_gpio()

    try:
        while True:
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

            # Log sensor data to the server
            log_sensor_data(sensor_data)

            # Fetch and update actuators
            fetch_and_update_actuators()

            # Delay between iterations
            time.sleep(10)

    except KeyboardInterrupt:
        print("Shutting down AquaGuard RPi Client...")
    except Exception as e:
        print(f"Unexpected error: {e}")
        traceback.print_exc()
    finally:
        GPIO.cleanup()
        spi.close()

if __name__ == "__main__":
    main_loop()
