import smbus2

def read_uv_sensor(i2c_address=0x38, bus_number=1):
    try:
        bus = smbus2.SMBus(bus_number)
        uv_data = bus.read_byte(i2c_address)
        return uv_data / 256.0
    except Exception as e:
        print(f"Error reading UV sensor: {e}")
        return 0
