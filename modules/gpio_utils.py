import RPi.GPIO as GPIO

# Define relay and digital sensor pin mappings
relay_pins = {
    'algicide_pump': 5,
    'chlorine_pump': 6,
    'soda_pump': 13,
    'pool_cover': 25,
    'water_in': 23,
    'water_out': 24
}


DIGITAL_SENSOR_PINS = {
    "water_level": 17,
    "motion": 27,
    "algicide_level": 22,
    "chlorine_level": 23,
    "soda_level": 24,
    "pool_tank_level": 18,
}


def initialize_gpio():
    """
    Initialize all GPIO pins for relays and sensors.
    """
    try:
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)

        # Relay output pins setup (OFF by default)
        for name, pin in relay_pins.items():
            GPIO.setup(pin, GPIO.OUT)
            GPIO.output(pin, GPIO.LOW)
            print(f"[⚙️ RELAY INIT] {name} (pin {pin}) set to OFF")

        # Digital input sensor pins setup
        for name, pin in DIGITAL_SENSOR_PINS.items():
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
            print(f"[📥 SENSOR INIT] {name} (pin {pin}) set as INPUT")

        print("[✅ GPIO INIT] All GPIO pins initialized.")
    except Exception as e:
        print(f"[❌ GPIO INIT ERROR] {e}")


def cleanup_gpio():
    """
    Safely reset all GPIO resources.
    """
    try:
        GPIO.cleanup()
        print("[✅ GPIO CLEANUP] GPIO resources released.")
    except Exception as e:
        print(f"[❌ GPIO CLEANUP ERROR] {e}")
