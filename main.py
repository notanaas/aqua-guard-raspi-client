import os
import time
from dotenv import load_dotenv
from modules.gpio_utils import initialize_gpio, cleanup_gpio
from modules.sensors import (
    read_adc,
    read_i2c_sensor,
    read_digital_sensor,
    log_sensor_data,
)
from modules.relays import control_relay, manage_pool_water_levels, manage_pool_tank, sync_actuators_with_server
from modules.device_settings import fetch_user_and_device_settings
from modules.blockchain import log_to_blockchain, sync_blockchain
from modules.notification import notify_server
from ai_logic.predictor import evaluate_rules, log_to_csv

# Load environment variables
load_dotenv()

# Environment variables
SERVER_BASE_URL = os.getenv("SERVER_BASE_URL")
SERIAL_NUMBER = os.getenv("SERIAL_NUMBER")
DEVICE_API_KEY = os.getenv("DEVICE_API_KEY")

if not SERVER_BASE_URL or not SERIAL_NUMBER or not DEVICE_API_KEY:
    raise ValueError("SERVER_BASE_URL, SERIAL_NUMBER, and DEVICE_API_KEY must be set in the environment variables.")

# I2C sensor addresses
I2C_ADDRESS_UV = 0x38
I2C_ADDRESS_ORP = 0x39

local_blockchain = []  # Blockchain for logging events

def main_loop():
    """Main loop for the AquaGuard system."""
    print("Starting AquaGuard System...")
    initialize_gpio()

    # Fetch device and user settings
    device_settings, user_settings = fetch_user_and_device_settings()

    if not device_settings or not user_settings:
        print("Exiting due to missing settings.")
        cleanup_gpio()
        return

    try:
        while True:
            # Step 1: Read sensors
            sensor_data = {
                "pH": read_adc(0),
                "temperature": read_adc(1),
                "uv": read_i2c_sensor(I2C_ADDRESS_UV),
                "orp": read_i2c_sensor(I2C_ADDRESS_ORP),
                "waterLevel": read_digital_sensor("water_level"),
                "poolTankLevel": read_digital_sensor("pool_tank_level"),
            }
            print(f"Sensor Data: {sensor_data}")

            # Step 2: Log sensor data
            log_sensor_data(sensor_data)
            log_to_blockchain("sensor_reading", sensor_data)

            # Step 3: Sync actuators with server
            sync_actuators_with_server()

            # Step 4: AI-based decision-making
            actions = evaluate_rules(sensor_data, user_settings)
            print(f"Evaluated Actions: {actions}")

            # Step 5: Execute actions
            for action in actions:
                control_relay(action["actuator"], action["command"])
                notify_server(
                    user_id=SERIAL_NUMBER,
                    message=action["message"],
                    notification_type="info" if action["command"] == "ON" else "warning",
                )

            # Step 6: Log actions to CSV
            log_to_csv(sensor_data, actions)

            # Step 7: Manage relays directly
            manage_pool_water_levels(sensor_data)
            manage_pool_tank(sensor_data)

            # Step 8: Sync blockchain with server if necessary
            if len(local_blockchain) >= 10:
                sync_blockchain()

            # Step 9: Wait before next iteration
            time.sleep(10)

    except KeyboardInterrupt:
        print("System shutting down.")
    except Exception as e:
        print(f"Unexpected error occurred: {e}")
    finally:
        cleanup_gpio()

if __name__ == "__main__":
    main_loop()
