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
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

# Relay pins
RELAY_PINS = {
    "water_in": 23,
    "water_out": 16,
    "chlorine_pump": 18,
    "filter_head": 22,
    "pool_cover": 25,  # Added pool cover actuator on GPIO 25
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
    """Send HTTP requests to the server."""
    url = f"{SERVER_BASE_URL}{endpoint}"
    headers = {
        "Content-Type": "application/json",
        "x-api-key": DEVICE_API_KEY,
        "x-serial-number": SERIAL_NUMBER,
    }
    try:
        if method.upper() == "GET":
            response = requests.get(url, headers=headers)
        elif method.upper() == "POST":
            response = requests.post(url, json=data, headers=headers)
        else:
            raise ValueError("Unsupported HTTP method.")
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"API request to {endpoint} failed: {e}")
        traceback.print_exc()
        return None

def read_digital_sensor(sensor_type):
    """Read data from a digital sensor."""
    pin = DIGITAL_SENSOR_PINS.get(sensor_type)
    if pin is None:
        raise ValueError(f"Invalid digital sensor type: {sensor_type}")
    try:
        return GPIO.input(pin)
    except Exception as e:
        print(f"Error reading digital sensor '{sensor_type}': {e}")
        return None

def read_adc(channel):
    """Read data from ADC channel."""
    try:
        adc = spi.xfer2([1, (8 + channel) << 4, 0])
        value = ((adc[1] & 3) << 8) + adc[2]
        return round(value * (3.3 / 1023), 2)  # Convert to voltage
    except Exception as e:
        print(f"Error reading ADC channel {channel}: {e}")
        return None

def read_uv_sensor(retries=3):
    """Read data from the UV sensor."""
    for attempt in range(retries):
        try:
            uv_data = i2c_bus.read_word_data(I2C_ADDRESS, 0x00)
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
        if relay_name == "pool_cover":  # Custom logic for pool cover
            if state.upper() == "OPEN":
                GPIO.output(pin, GPIO.HIGH)  # Activate relay to open the cover
            elif state.upper() == "CLOSE":
                GPIO.output(pin, GPIO.LOW)   # Deactivate relay to close the cover
            else:
                print(f"Invalid state for pool_cover: {state}")
        else:
            GPIO.output(pin, GPIO.HIGH if state.upper() == "ON" else GPIO.LOW)
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

def check_gpio_connection(pin, mode="input"):
    """
    Check if a GPIO pin is configured and potentially connected to a device.
    Args:
        pin: GPIO pin number (BCM mode).
        mode: "input" to check input status, "output" to test feedback.
    Returns:
        str: Status of the GPIO pin.
    """
    try:
        if mode == "input":
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
            state = GPIO.input(pin)
            return f"GPIO {pin} is configured as INPUT. Current state: {'HIGH' if state else 'LOW'}."
        elif mode == "output":
            GPIO.setup(pin, GPIO.OUT)
            GPIO.output(pin, GPIO.HIGH)
            state = GPIO.input(pin)  # Check feedback
            GPIO.output(pin, GPIO.LOW)
            return f"GPIO {pin} is configured as OUTPUT. Feedback state: {'HIGH' if state else 'LOW'}."
        else:
            return f"Invalid mode specified for GPIO {pin}. Use 'input' or 'output'."
    except Exception as e:
        return f"Error testing GPIO {pin}: {e}"

def main_loop():
    """Main loop for reading sensors, checking GPIO, and controlling relays."""
    print("Starting AquaGuard RPi Client...")
    try:
        while True:
            # Verify GPIO connections
            for relay_name, pin in RELAY_PINS.items():
                status = check_gpio_connection(pin, mode="output")
                print(f"[Relay Check] {relay_name}: {status}")

            for sensor_name, pin in DIGITAL_SENSOR_PINS.items():
                status = check_gpio_connection(pin, mode="input")
                print(f"[Sensor Check] {sensor_name}: {status}")

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
