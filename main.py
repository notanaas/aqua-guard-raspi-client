import sys
import os
import time
import json
sys.path.append(os.path.abspath(os.path.dirname(__file__)))
from actuators.relay_control import control_relay
from sensors.adc import ADC
from sensors.uv_sensor import read_uv_sensor
from blockchain.blockchain_client import BlockchainClient
from utils import initialize_csv, rotate_log, read_dynamic_settings, save_settings

# Initialize Settings
settings = read_dynamic_settings()

# Initialize Blockchain Client
blockchain = BlockchainClient(
    settings['blockchain_url'],
    settings['contract_address'],
    settings['contract_abi'],
    settings['serial_number']
)

def main_loop():
    initialize_csv()
    print("Starting AquaGuard RPi Client...")

    while True:
        try:
            # Read Sensors
            sensor_data = {
                "pH": read_adc(0),
                "temperature": read_adc(1),
                "pressure": read_adc(2),
                "current": read_adc(3),
                "waterLevel": settings['gpio_pins']['water_switch'],
                "uv": read_uv_sensor(),
                "motion": settings['gpio_pins']['motion_sensor']
            }
            print(f"Sensor Data: {sensor_data}")

            # Log Data to Blockchain
            blockchain.log_sensor_data(sensor_data)

            # Rotate Log File if Necessary
            rotate_log()

            # Sleep before next iteration
            time.sleep(settings['read_interval'])
        except KeyboardInterrupt:
            print("Shutting down AquaGuard RPi Client...")
            break
        except Exception as e:
            print(f"Error in main loop: {e}")

if __name__ == "__main__":
    main_loop()
