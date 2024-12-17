const wpi = require('wiring-pi'); // Use wiring-pi for GPIO control
const axios = require('axios');
const fs = require('fs');
const path = require('path');
require('dotenv').config();
const { evaluateRules, sendActionsToActuators } = require('./kbs');

// Environment Variables
const SERVER_URL = process.env.MAIN_SERVER_URL || 'http://localhost:3001';
const DEVICE_SERIAL = process.env.DEVICE_SERIAL || 'DEFAULT_SERIAL';
const LOG_FILE = path.join(__dirname, 'logs', 'sensor_actions_log.csv');

// Initialize WiringPi GPIO
wpi.setup('gpio');

// GPIO Pin Definitions
const PIN_WATER_SWITCH = 17; // Input
const PIN_MOTION_SENSOR = 27; // Input
const PIN_RELAY_WATER_IN = 18; // Output
const PIN_RELAY_WATER_OUT = 23; // Output
const PIN_RELAY_CHLORINE_PUMP = 24; // Output
const PIN_RELAY_FILTER_HEAD = 25; // Output

// Pin Setup
wpi.pinMode(PIN_WATER_SWITCH, wpi.INPUT);
wpi.pinMode(PIN_MOTION_SENSOR, wpi.INPUT);
wpi.pinMode(PIN_RELAY_WATER_IN, wpi.OUTPUT);
wpi.pinMode(PIN_RELAY_WATER_OUT, wpi.OUTPUT);
wpi.pinMode(PIN_RELAY_CHLORINE_PUMP, wpi.OUTPUT);
wpi.pinMode(PIN_RELAY_FILTER_HEAD, wpi.OUTPUT);

// Initialize CSV Logging
function initializeCSV() {
  if (!fs.existsSync(LOG_FILE)) {
    fs.writeFileSync(LOG_FILE, 'Timestamp,pH,Temperature,Pressure,WaterLevel,Motion,Actions\n');
  }
}

// Mock Sensor Data for Testing
function readSensorData() {
  return {
    pH: (Math.random() * 14).toFixed(2), // pH value between 0 and 14
    temperature: (20 + Math.random() * 10).toFixed(2), // Temperature between 20-30°C
    pressure: (Math.random() * 100).toFixed(2), // Pressure value
    waterLevel: wpi.digitalRead(PIN_WATER_SWITCH) ? 100 : 0,
    motion: wpi.digitalRead(PIN_MOTION_SENSOR),
    chlorineLevel: 2,
    turbidity: 30,
    weatherForecast: 'sunny',
    poolBeingCleaned: false,
  };
}

// Control Relays Based on Actions
function controlActuators(actions) {
  const relayMap = {
    waterFillPump: PIN_RELAY_WATER_IN,
    waterDrainPump: PIN_RELAY_WATER_OUT,
    chlorinePump: PIN_RELAY_CHLORINE_PUMP,
    filterMotor: PIN_RELAY_FILTER_HEAD,
  };

  actions.forEach(({ actuator, command, message }) => {
    if (relayMap[actuator] !== undefined) {
      wpi.digitalWrite(relayMap[actuator], command ? wpi.HIGH : wpi.LOW);
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
    const sensorData = readSensorData();
    console.log('Collected Sensor Data:', sensorData);

    // Apply Local KBS Rules
    const actions = evaluateRules(sensorData, { poolInfo: { minWaterLevel: 30, maxWaterLevel: 80, desiredTemperature: 28 } });
    controlActuators(actions);
    logToCSV(sensorData, actions);

    // Send Sensor Data to Server
    const res = await axios.post(`${SERVER_URL}/sensor-data`, sensorData, {
      headers: { serialNumber: DEVICE_SERIAL },
    });
    console.log('Server Response:', res.data);

    // Execute Actions Sent by the Server
    if (res.data.actions) {
      sendActionsToActuators(res.data.actions);
    }
  } catch (error) {
    console.error('Error in sendSensorData:', error.message);
  }
}

// Main Execution Loop
initializeCSV();
setInterval(sendSensorData, 5000);
console.log('Sensor Monitoring Initialized. Sending data every 5 seconds...');
