const axios = require('axios');
const {Gpio} = require('bindings')('pigpio.node');const fs = require('fs');
const path = require('path');
require('dotenv').config();
const { evaluateRules, sendActionsToActuators } = require('./kbs'); // Import KBS

// Environment Variables
const SERVER_URL = process.env.MAIN_SERVER_URL || 'http://localhost:3001'; // Default local server
const DEVICE_SERIAL = process.env.DEVICE_SERIAL || 'DEFAULT_SERIAL';
const LOG_FILE = path.join(__dirname, 'logs', 'sensor_actions_log.csv');

// GPIO Pins Configuration
const waterLevelSwitch = new Gpio(17, { mode: Gpio.INPUT });
const motionSensor = new Gpio(27, { mode: Gpio.INPUT });

// GPIO Relays for Actuators
const relayWaterIn = new Gpio(18, { mode: Gpio.OUTPUT });
const relayWaterOut = new Gpio(23, { mode: Gpio.OUTPUT });
const relayChlorinePump = new Gpio(24, { mode: Gpio.OUTPUT });
const relayFilterHead = new Gpio(25, { mode: Gpio.OUTPUT });

// Placeholder for SPI ADC0834 - pigpio doesn't directly handle SPI
const spi = require('pigpio').spi; // Simulated SPI placeholder
let adc; // Placeholder for SPI communication setup

// Initialize CSV Logging
function initializeCSV() {
  if (!fs.existsSync(LOG_FILE)) {
    fs.writeFileSync(LOG_FILE, 'Timestamp,pH,Temperature,Pressure,WaterLevel,Motion,Actions\n');
  }
}

// Placeholder: SPI ADC Reading (needs actual implementation for ADC0834)
function readADC(channel) {
  // Mock return for ADC values (simulate sensor voltages)
  return (Math.random() * 3.3).toFixed(2);
}

// Collect All Sensor Data
async function collectSensorData() {
  return {
    pH: (readADC(0) * 2).toFixed(2),           // CH0: pH Sensor
    temperature: (readADC(1) * 10).toFixed(2), // CH1: Temperature Sensor
    pressure: (readADC(2) * 50).toFixed(2),    // CH2: Pressure Sensor
    waterLevel: waterLevelSwitch.digitalRead() ? 100 : 0, // Float switch
    motion: motionSensor.digitalRead(),        // Motion detected (1/0)
    chlorineLevel: 2,                          // Example chlorine level (hardcoded)
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
      relayMap[actuator].digitalWrite(command ? 1 : 0);
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
  try {
    const sensorData = await collectSensorData();
    console.log('Collected Sensor Data:', sensorData);

    // Apply Local KBS
    const actions = evaluateRules(sensorData, { poolInfo: { minWaterLevel: 30, maxWaterLevel: 80, desiredTemperature: 28 } });
    controlActuators(actions);
    logToCSV(sensorData, actions);

    // Send Sensor Data to Server
    const res = await axios.post(`${SERVER_URL}/sensor-data`, sensorData, {
      headers: { serialNumber: DEVICE_SERIAL },
    });
    console.log('Server Response:', res.data);

    // Send Actions from Server to Actuators
    if (res.data.actions) {
      await sendActionsToActuators(res.data.actions);
    }
  } catch (error) {
    console.error('Error in sendSensorData:', error.message);
  }
}

// Main Execution: Initialize CSV and Start Loop
initializeCSV();
setInterval(sendSensorData, 5000);
console.log('Sensor Monitoring Initialized. Sending data every 5 seconds...');
