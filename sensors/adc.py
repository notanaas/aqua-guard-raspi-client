import spidev
import time

class ADC:
    def __init__(self, bus=0, device=0):
        """
        Initialize the SPI interface.
        :param bus: SPI bus number (default 0)
        :param device: SPI device (default 0)
        """
        self.spi = spidev.SpiDev()
        self.spi.open(bus, device)
        self.spi.max_speed_hz = 1350000  # Set SPI speed

    def read_channel(self, channel):
        """
        Read data from an ADC channel.
        :param channel: ADC channel number (0-3 for ADC0834)
        :return: The digital value (0-255) read from the channel
        """
        if channel < 0 or channel > 3:
            raise ValueError("Invalid channel. Must be between 0 and 3.")

        # Construct the command to send to ADC0834
        start_bit = 1
        single_ended = 1  # Single-ended mode
        command = [start_bit, (8 + channel) << 4, 0]

        # Send the command and receive the response
        response = self.spi.xfer2(command)

        # Process the response to extract the 8-bit value
        result = ((response[1] & 3) << 8) + response[2]
        return result

    def close(self):
        """
        Close the SPI interface.
        """
        self.spi.close()


# Example usage
if __name__ == "__main__":
    adc = ADC()

    try:
        while True:
            for channel in range(4):
                value = adc.read_channel(channel)
                print(f"Channel {channel}: {value}")
            time.sleep(1)
    except KeyboardInterrupt:
        print("Exiting...")
    finally:
        adc.close()
