import RPi.GPIO as GPIO

GPIO.setmode(GPIO.BCM)

# Setup Relay Pins
def setup_relays(relay_pins):
    for pin in relay_pins.values():
        GPIO.setup(pin, GPIO.OUT)
        GPIO.output(pin, GPIO.LOW)

def control_relay(relay_pins, relay_name, command):
    try:
        if relay_name in relay_pins:
            GPIO.output(relay_pins[relay_name], GPIO.HIGH if command == "ON" else GPIO.LOW)
            print(f"Relay {relay_name} set to {command}")
        else:
            print(f"Relay {relay_name} not found.")
    except Exception as e:
        print(f"Error controlling relay {relay_name}: {e}")
