import os

PRIMARY_SERVER = os.getenv("PRIMARY_SERVER", "http://192.168.1.15:3001")
BACKUP_SERVER = os.getenv("BACKUP_SERVER", "http://localhost:3001")
DEVICE_SERIAL = os.getenv("DEVICE_SERIAL", "UNKNOWN_SERIAL")
DEVICE_PASSWORD = os.getenv("DEVICE_PASSWORD", "default_password")
LOG_FILE = os.path.join(os.path.dirname(__file__), "logs/sensor_actions_log.csv")
