import sys
import os
import time
import json
import traceback
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

# Import custom modules
from actuators.relay_control import control_relay
from sensors.adc import read_adc
from sensors.uv_sensor import read_uv_sensor
from blockchain.blockchain_client import BlockchainClient
from utils import initialize_csv, rotate_log, read_dynamic_settings, save_settings

# Initialize Settings
try:
    settings = read_dynamic_settings()
    print("Settings loaded successfully.")
except Exception as e:
    print(f"Error loading settings: {e}")
    sys.exit(1)

# Initialize Blockchain Client
try:
    blockchain = BlockchainClient(
        settings['blockchain_url'],
        settings['contract_address'],
        settings['contract_abi'],
        settings['serial_number']
    )
    print("Blockchain client initialized successfully.")
except Exception as e:
    print(f"Error initializing blockchain client: {e}")
    sys.exit(1)

def main_loop():
    """
    Main loop for reading sensor data, logging to the blockchain,
    and handling periodic tasks.
    """
    try:
        initialize_csv()
        print("Starting AquaGuard RPi Client...")
    except Exception as e:
        print(f"Error during initialization: {e}")
        return

    while True:
        try:
            # Read Sensors
            sensor_data = {
                "pH": read_adc(0),
                "temperature": read_adc(1),
                "pressure": read_adc(2),
                "current": read_adc(3),
                "waterLevel": settings['gpio_pins'].get('water_switch', None),
                "uv": read_uv_sensor(),
                "motion": settings['gpio_pins'].get('motion_sensor', None)
            }
            print(f"Sensor Data: {sensor_data}")

            # Log Data to Blockchain
            try:
                blockchain.log_sensor_data(sensor_data)
                print("Sensor data logged to blockchain.")
            except Exception as e:
                print(f"Error logging data to blockchain: {e}")
                traceback.print_exc()

            # Rotate Log File if Necessary
            try:
                rotate_log()
            except Exception as e:
                print(f"Error rotating log file: {e}")

            # Sleep before next iteration
            time.sleep(settings.get('read_interval', 5))

        except KeyboardInterrupt:
            print("Shutting down AquaGuard RPi Client...")
            break
        except Exception as e:
            print(f"Unexpected error in main loop: {e}")
            traceback.print_exc()

if __name__ == "__main__":
    try:
        main_loop()
    except Exception as e:
        print(f"Critical error: {e}")
    finally:
        # Cleanup resources (e.g., GPIO)
        print("Cleaning up resources...")
