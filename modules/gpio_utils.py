import RPi.GPIO as GPIO

# Define relay and digital sensor pin mappings
RELAY_PINS = {
    "algicide_pump": 5,
    "chlorine_pump": 6,
    "soda_pump": 13,
    "pool_cover": 25,
    "water_in": 23,
    "water_out": 24,
    "pool_tank_fill": 19,
    "pool_tank_drain": 26,
    "filter_head": 21,     # ✅ Add this
    "pool_heater": 20      # ✅ Add this too, used in AI logic
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
    Initialize GPIO pins.
    
    Sets up relay and digital sensor pins with default states.
    """
    GPIO.cleanup()
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    
    # Initialize relay pins
    for pin in RELAY_PINS.values():
        GPIO.setup(pin, GPIO.OUT, initial=GPIO.HIGH)  # Relays OFF by default
    
    # Initialize digital sensor pins
    for pin in DIGITAL_SENSOR_PINS.values():
        GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    
    print("GPIO initialization complete.")

def cleanup_gpio():
    """
    Clean up GPIO pins.
    
    Releases GPIO resources and resets all pins.
    """
    GPIO.cleanup()
    print("GPIO cleaned up.")
