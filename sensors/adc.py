import spidev

class ADC:
    def __init__(self, bus=0, device=0):
        self.spi = spidev.SpiDev()
        self.spi.open(bus, device)
        self.spi.max_speed_hz = 1350000

    def read_channel(self, channel):
        if channel < 0 or channel > 3:
            raise ValueError("Invalid channel. Must be between 0 and 3.")

        command = [1, (8 + channel) << 4, 0]
        response = self.spi.xfer2(command)
        result = ((response[1] & 3) << 8) + response[2]
        return result

    def close(self):
        self.spi.close()

# Alias for read_channel
def read_adc(channel):
    adc = ADC()
    try:
        return adc.read_channel(channel)
    finally:
        adc.close()
