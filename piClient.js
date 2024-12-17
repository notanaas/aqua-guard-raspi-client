const axios = require('axios');
const { Gpio } = require('onoff');
const spi = require('spi-device');
require('dotenv').config();

// Environment Variables
const SERVER_URL = process.env.MAIN_SERVER_URL; // Main Server URL
const DEVICE_SERIAL = process.env.DEVICE_SERIAL; // Device Serial Number

// GPIO Pins Configuration
const waterLevelSwitch = new Gpio(17, 'in'); // Water level float switch
const motionSensor = new Gpio(27, 'in');     // Motion detection sensor

// GPIO Relays for Actuators
const relayWaterIn = new Gpio(18, 'out');      // Relay for water fill pump
const relayWaterOut = new Gpio(23, 'out');     // Relay for water drainage pump
const relayChlorinePump = new Gpio(24, 'out'); // Relay for chlorine pump
const relayFilterHead = new Gpio(25, 'out');   // Relay for filter head adjustment

// SPI ADC0834 Configuration
const adc = spi.openSync(0, 0, { maxSpeedHz: 1000000 });

// Function to Read from ADC0834
function readADC(channel) {
  if (channel < 0 || channel > 3) throw new Error('Invalid ADC Channel');

  const command = Buffer.from([1, (8 + channel) << 4, 0]);
  const response = Buffer.alloc(3);

  adc.transferSync([{ sendBuffer: command, receiveBuffer: response, byteLength: 3 }]);
  const value = ((response[1] & 3) << 8) + response[2];
  return (value * 3.3) / 255; // Convert to voltage (0-3.3V)
}

// Collect All Sensor Data
async function collectSensorData() {
  return {
    pH: (readADC(0) * 2).toFixed(2),        // Scaled for pH sensor
    temperature: (readADC(1) * 10).toFixed(2), // Temperature sensor scaling
    pressure: (readADC(2) * 50).toFixed(2),    // Pressure scaling
    current: (readADC(3) * 10).toFixed(2),     // Current sensor scaling
    waterLevel: waterLevelSwitch.readSync() ? 100 : 0, // Float switch (0% or 100%)
    motion: motionSensor.readSync(),          // Motion detected (1/0)
  };
}

// Send Sensor Data to Main Server
async function sendSensorData() {
  const sensorData = await collectSensorData();
  console.log('Sending Sensor Data:', sensorData);

  try {
    const response = await axios.post(`${SERVER_URL}/sensor-data`, sensorData, {
      headers: { serialNumber: DEVICE_SERIAL },
    });
    console.log('Server Response:', response.data);

    if (response.data.actions) controlActuators(response.data.actions);
  } catch (error) {
    console.error('Error sending sensor data:', error.message);
  }
}

// Control Relays Based on Server Commands
function controlActuators(actions) {
  actions.forEach(({ actuator, command }) => {
    const relayMap = {
      waterFillPump: relayWaterIn,
      waterDrainPump: relayWaterOut,
      chlorinePump: relayChlorinePump,
      filterMotor: relayFilterHead,
    };

    if (relayMap[actuator]) {
      relayMap[actuator].writeSync(command === 'ON' ? 1 : 0);
      console.log(`Actuator ${actuator} set to ${command}`);
    }
  });
}

// Main Loop to Send Data Every 5 Seconds
setInterval(sendSensorData, 5000);
