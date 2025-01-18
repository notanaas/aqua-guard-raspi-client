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
    "algicide_pump": 5,
    "chlorine_pump": 6,
    "soda_pump": 13,
    "pool_cover": 25,
    "water_in": 23,  # Relay for filling water into the pool
    "water_out": 24,  # Relay for draining water out of the pool
    "pool_tank_fill": 19,  # Relay for filling water from the pool tank
    "pool_tank_drain": 26,  # Relay for draining water to the pool tank
}

# Digital sensor pins for level detection
DIGITAL_SENSOR_PINS = {
    "water_level": 17,
    "motion": 27,
    "algicide_level": 22,
    "chlorine_level": 23,
    "soda_level": 24,
    "pool_tank_level": 18,
}

# ADC0834 Setup
spi = spidev.SpiDev()
spi.open(0, 0)
spi.max_speed_hz = 500000
spi.mode = 0

# I2C Setup for UV and ORP sensors
I2C_ADDRESS_UV = 0x38
I2C_ADDRESS_ORP = 0x39
i2c_bus = smbus.SMBus(1)

def initialize_gpio():
    """Initialize GPIO pins."""
    GPIO.cleanup()
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    for pin in RELAY_PINS.values():
        GPIO.setup(pin, GPIO.OUT, initial=GPIO.LOW)
    for pin in DIGITAL_SENSOR_PINS.values():
        GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    print("GPIO initialization complete.")

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
        raw_value = ((adc[1] & 0x03) << 8) + adc[2]
        voltage = (raw_value / 1023.0) * 3.3
        print(f"ADC Channel {channel} Value: {raw_value}, Voltage: {voltage:.2f}V")
        return round(voltage, 2)
    except Exception as e:
        print(f"Error reading ADC channel {channel}: {e}")
        return None

def read_uv_sensor(retries=3):
    """Read data from the UV sensor."""
    for attempt in range(retries):
        try:
            uv_data = i2c_bus.read_word_data(I2C_ADDRESS_UV, 0x00)
            print(f"UV Sensor Data: {uv_data}")
            return uv_data
        except Exception as e:
            print(f"Error reading UV sensor on attempt {attempt + 1}/{retries}: {e}")
            time.sleep(1)
    print("Failed to read UV sensor after multiple attempts.")
    return None

def read_orp_sensor(retries=3):
    """Read data from the ORP sensor."""
    for attempt in range(retries):
        try:
            orp_data = i2c_bus.read_word_data(I2C_ADDRESS_ORP, 0x00)
            print(f"ORP Sensor Data: {orp_data}")
            return orp_data
        except Exception as e:
            print(f"Error reading ORP sensor on attempt {attempt + 1}/{retries}: {e}")
            time.sleep(1)
    print("Failed to read ORP sensor after multiple attempts.")
    return None

def control_relay(relay_name, state):
    """Control relay states."""
    pin = RELAY_PINS.get(relay_name)
    if pin is None:
        print(f"Invalid relay name: {relay_name}")
        return
    try:
        GPIO.output(pin, GPIO.LOW if state.upper() == "ON" else GPIO.HIGH)
        print(f"Relay '{relay_name}' set to {state}")
    except Exception as e:
        print(f"Error controlling relay '{relay_name}': {e}")

def manage_pool_water_levels(sensor_data):
    """Control water in and out relays based on pool water level."""
    if not sensor_data["waterLevel"]:  # If water level is low
        print("Water level is low, filling water into the pool...")
        control_relay("water_in", "ON")
        control_relay("water_out", "OFF")
    elif sensor_data["poolTankLevel"] == 0:  # If pool tank is full
        print("Draining water from the pool...")
        control_relay("water_out", "ON")
        control_relay("water_in", "OFF")
    else:
        print("Water level is stable.")
        control_relay("water_in", "OFF")
        control_relay("water_out", "OFF")

def manage_pool_tank(sensor_data):
    """Control pool tank filling or draining."""
    if not sensor_data["poolTankLevel"]:  # If the pool tank level is low
        print("Pool tank level is low, filling the tank...")
        control_relay("pool_tank_fill", "ON")
        control_relay("pool_tank_drain", "OFF")
    elif sensor_data["poolTankLevel"] == 1:  # If the pool tank is full
        print("Draining excess water from the tank...")
        control_relay("pool_tank_drain", "ON")
        control_relay("pool_tank_fill", "OFF")
    else:
        print("Pool tank level is stable.")
        control_relay("pool_tank_fill", "OFF")
        control_relay("pool_tank_drain", "OFF")

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




def log_to_blockchain(event_type, data):
    """Log events to the blockchain."""
    prev_hash = local_blockchain[-1]["hash"] if local_blockchain else "0"
    block = {
        "timestamp": time.time(),
        "event_type": event_type,
        "data": data,
        "previous_hash": prev_hash,
        "hash": hashlib.sha256(f"{data}{prev_hash}".encode()).hexdigest(),
    }
    local_blockchain.append(block)
    print(f"Blockchain Log: {block}")

def fetch_user_and_device_settings():
    """Fetch user and device settings via API."""
    headers = {
        "x-serial-number": SERIAL_NUMBER,
        "x-api-key": DEVICE_API_KEY,
    }
    try:
        response = requests.get(f"{SERVER_BASE_URL}/api/device/user-and-settings", headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        log_to_blockchain("fetch_user_settings", data)
        return data.get("device_settings"), data.get("user_settings")
    except requests.RequestException as e:
        print(f"Failed to fetch user settings: {e}")
        log_to_blockchain("error", {"action": "fetch_user_settings", "error": str(e)})
        return None, None

def sync_blockchain():
    """Sync the local blockchain with the server."""
    headers = {
        "x-serial-number": SERIAL_NUMBER,
        "x-api-key": DEVICE_API_KEY,
    }
    try:
        response = requests.post(
            f"{SERVER_BASE_URL}/api/device/blockchain/sync",
            json={"blockchain": local_blockchain},
            headers=headers,
            timeout=10,
        )
        response.raise_for_status()
        local_blockchain.clear()
        print("Blockchain synced successfully.")
    except requests.RequestException as e:
        print(f"Failed to sync blockchain: {e}")

def read_i2c_sensor(address):
    """Read data from I2C sensors."""
    try:
        return i2c_bus.read_word_data(address, 0x00)
    except Exception as e:
        print(f"Error reading I2C sensor at address {address}: {e}")
        return None

def notify_server(user_id, message, notification_type="info"):
    """Send a notification to the server."""
    headers = {
        "x-serial-number": SERIAL_NUMBER,
        "x-api-key": DEVICE_API_KEY,
    }
    try:
        payload = {
            "user": user_id,
            "message": message,
            "type": notification_type,
        }
        response = requests.post(
            f"{SERVER_BASE_URL}/api/notifications/create",
            json=payload,
            headers=headers,
            timeout=10,
        )
        response.raise_for_status()
        print(f"Notification sent: {message}")
    except requests.RequestException as e:
        print(f"Failed to send notification: {e}")

def main_loop():
    """Main loop for reading sensors, making decisions, and controlling relays."""
    print("Starting AquaGuard System...")
    initialize_gpio()
    device_settings, user_settings = fetch_user_and_device_settings()

    if not device_settings or not user_settings:
        print("Exiting due to missing settings.")
        return

    try:
        while True:
            sensor_data = {
                "pH": read_adc(0),
                "temperature": read_adc(1),
                "uv": read_i2c_sensor(I2C_ADDRESS_UV),
                "orp": read_i2c_sensor(I2C_ADDRESS_ORP),
                "water_level": read_digital_sensor("water_level"),
            }
            print(f"Sensor Data: {sensor_data}")

            log_to_blockchain("sensor_reading", sensor_data)

            if sensor_data["pH"] < user_settings["preferred_pH_range"][0]:
                control_relay("soda_pump", "ON")
                notify_server(USER_ID, "pH level low: Adjusting soda pump.", "warning")
            else:
                control_relay("soda_pump", "OFF")

            if len(local_blockchain) >= 10:
                sync_blockchain()

            time.sleep(10)

    except KeyboardInterrupt:
        print("System shutting down.")
    finally:
        GPIO.cleanup()
        spi.close()

if __name__ == "__main__":
    main_loop()