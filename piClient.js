const axios = require('axios');
const { Gpio } = require('onoff');
const spi = require('spi-device');
const fs = require('fs');
const path = require('path');
require('dotenv').config();
const { evaluateRules, sendActionsToActuators } = require('./kbs'); // Import KBS

// Environment Variables
const SERVER_URL = process.env.MAIN_SERVER_URL; // Main Server URL
const DEVICE_SERIAL = process.env.DEVICE_SERIAL; // Device Serial Number
const LOG_FILE = path.join(__dirname, 'logs', 'sensor_actions_log.csv');

// GPIO Pins Configuration
const waterLevelSwitch = new Gpio(17, 'in'); // GPIO 17 (BCM Numbering)
const motionSensor = new Gpio(27, 'in');     // Motion detection sensor

// GPIO Relays for Actuators
const relayWaterIn = new Gpio(18, 'out');      // Relay for water fill pump
const relayWaterOut = new Gpio(23, 'out');     // Relay for water drainage pump
const relayChlorinePump = new Gpio(24, 'out'); // Relay for chlorine pump
const relayFilterHead = new Gpio(25, 'out');   // Relay for filter head adjustment

// SPI ADC0834 Configuration
const adc = spi.openSync(0, 0, { maxSpeedHz: 1000000 });

// Initialize CSV Logging
function initializeCSV() {
  if (!fs.existsSync(LOG_FILE)) {
    fs.writeFileSync(LOG_FILE, 'Timestamp,pH,Temperature,Pressure,WaterLevel,Motion,Actions\n');
  }
}

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
    pH: (readADC(0) * 2).toFixed(2),           // CH0: pH Sensor
    temperature: (readADC(1) * 10).toFixed(2), // CH1: Temperature Sensor
    pressure: (readADC(2) * 50).toFixed(2),    // CH2: Pressure Sensor
    waterLevel: waterLevelSwitch.readSync() ? 100 : 0, // Float switch (0% or 100%)
    motion: motionSensor.readSync(),           // Motion detected (1/0)
    chlorineLevel: 2,                          // Example chlorine level (hardcoded for now)
    turbidity: 30,                             // Example turbidity value
    weatherForecast: 'sunny',                  // Example weather data
    poolBeingCleaned: false                    // Pool cleaning state
  };
}

// Control Relays Based on Actions
function controlActuators(actions) {
  const relayMap = {
    waterFillPump: relayWaterIn,
    waterDrainPump: relayWaterOut,
    chlorinePump: relayChlorinePump,
    filterMotor: relayFilterHead,
  };

  actions.forEach(({ actuator, command, message }) => {
    if (relayMap[actuator]) {
      relayMap[actuator].writeSync(command ? 1 : 0);
      console.log(`Actuator ${actuator} set to ${command ? 'ON' : 'OFF'} - ${message}`);
    }
  });
}

// Log Data to CSV
function logToCSV(sensorData, actions) {
  const timestamp = new Date().toISOString();
  const actionSummary = actions.map(a => `${a.actuator}:${a.command}`).join('|');

  const logEntry = `${timestamp},${sensorData.pH},${sensorData.temperature},${sensorData.pressure},${sensorData.waterLevel},${sensorData.motion},${actionSummary}\n`;
  fs.appendFileSync(LOG_FILE, logEntry);
  console.log('Logged to CSV:', logEntry.trim());
}

// Send Sensor Data to Main Server
async function sendSensorData() {
  const sensorData = await collectSensorData();
  console.log('Collected Sensor Data:', sensorData);

  // Apply Local KBS
  const actions = evaluateRules(sensorData, { poolInfo: { minWaterLevel: 30, maxWaterLevel: 80, desiredTemperature: 28 } });
  controlActuators(actions);
  logToCSV(sensorData, actions);

  // Send Actions to Server
  try {
    const res = await axios.post(`${SERVER_URL}/sensor-data`, sensorData, {
      headers: { serialNumber: DEVICE_SERIAL },
    });
    console.log('Server Response:', res.data);
    if (res.data.actions) await sendActionsToActuators(res.data.actions);
  } catch (error) {
    console.error('Error sending data to server:', error.message);
  }
}

// Main Loop to Send Data Every 5 Seconds
initializeCSV();
setInterval(sendSensorData, 5000);
