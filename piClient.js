const { Gpio } = require('onoff'); // Use 'onoff' for GPIO pin handling
const axios = require('axios');
const fs = require('fs');
const path = require('path');
require('dotenv').config();
const { evaluateRules, sendActionsToActuators } = require('./kbs'); // Import KBS

// Environment Variables
const SERVER_URL = process.env.MAIN_SERVER_URL || 'http://localhost:3001'; // Default local server
const DEVICE_SERIAL = process.env.DEVICE_SERIAL || 'DEFAULT_SERIAL';
const LOG_FILE = path.join(__dirname, 'logs', 'sensor_actions_log.csv');

// GPIO Pins Configuration
const waterLevelSwitch = new Gpio(17, 'in', 'both'); // Input with interrupt
const motionSensor = new Gpio(27, 'in', 'both');

// GPIO Relays for Actuators
const relayWaterIn = new Gpio(18, 'out');
const relayWaterOut = new Gpio(23, 'out');
const relayChlorinePump = new Gpio(24, 'out');
const relayFilterHead = new Gpio(25, 'out');

// Initialize CSV Logging
function initializeCSV() {
  if (!fs.existsSync(LOG_FILE)) {
    fs.writeFileSync(LOG_FILE, 'Timestamp,pH,Temperature,Pressure,WaterLevel,Motion,Actions\n');
  }
}

// Simulated ADC Reading (as 'onoff' doesn't handle SPI)
function readADC(channel) {
  return (Math.random() * 3.3).toFixed(2); // Mock sensor values
}

// Collect All Sensor Data
async function collectSensorData() {
  return {
    pH: (readADC(0) * 2).toFixed(2),
    temperature: (readADC(1) * 10).toFixed(2),
    pressure: (readADC(2) * 50).toFixed(2),
    waterLevel: waterLevelSwitch.readSync(), // Float switch status
    motion: motionSensor.readSync(), // Motion sensor status
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
  try {
    const sensorData = await collectSensorData();
    console.log('Collected Sensor Data:', sensorData);

    const actions = evaluateRules(sensorData, { poolInfo: { minWaterLevel: 30, maxWaterLevel: 80, desiredTemperature: 28 } });
    controlActuators(actions);
    logToCSV(sensorData, actions);

    const res = await axios.post(`${SERVER_URL}/sensor-data`, sensorData, {
      headers: { serialNumber: DEVICE_SERIAL },
    });
    console.log('Server Response:', res.data);

    if (res.data.actions) {
      await sendActionsToActuators(res.data.actions);
    }
  } catch (error) {
    console.error('Error in sendSensorData:', error.message);
  }
}

// Main Execution
initializeCSV();
setInterval(sendSensorData, 5000);
console.log('Sensor Monitoring Initialized. Sending data every 5 seconds...');
