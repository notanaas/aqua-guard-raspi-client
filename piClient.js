const { init } = require('raspi');
const { DigitalInput, DigitalOutput, HIGH, LOW } = require('raspi-gpio');
const axios = require('axios');
const fs = require('fs');
const path = require('path');
require('dotenv').config();
const { evaluateRules, sendActionsToActuators } = require('./kbs');

// Environment Variables
const SERVER_URL = process.env.MAIN_SERVER_URL || 'http://localhost:3001';
const DEVICE_SERIAL = process.env.DEVICE_SERIAL || 'DEFAULT_SERIAL';
const LOG_FILE = path.join(__dirname, 'logs', 'sensor_actions_log.csv');

// GPIO Pin Definitions
let waterSwitch, motionSensor, relayWaterIn, relayWaterOut, relayChlorinePump, relayFilterHead;

// Validate Environment Variables
if (!process.env.MAIN_SERVER_URL) {
  console.warn('Warning: MAIN_SERVER_URL is not set. Using default localhost.');
}
if (!process.env.DEVICE_SERIAL) {
  console.warn('Warning: DEVICE_SERIAL is not set. Using DEFAULT_SERIAL.');
}

// Initialize CSV Logging
function initializeCSV() {
  if (!fs.existsSync(LOG_FILE)) {
    fs.writeFileSync(LOG_FILE, 'Timestamp,pH,Temperature,Pressure,WaterLevel,Motion,Actions\n');
    console.log('Created log file:', LOG_FILE);
  }
}

// Simulated Sensor Data
function readSensorData() {
  try {
    return {
      pH: (Math.random() * 14).toFixed(2),
      temperature: (20 + Math.random() * 10).toFixed(2),
      pressure: (Math.random() * 100).toFixed(2),
      waterLevel: waterSwitch.read() === HIGH ? 100 : 0,
      motion: motionSensor.read() === HIGH ? 1 : 0,
      chlorineLevel: 2, // Placeholder
      turbidity: 30, // Placeholder
      weatherForecast: 'sunny',
      poolBeingCleaned: false,
    };
  } catch (error) {
    console.error('Error reading sensor data:', error.message);
    return {
      pH: 0,
      temperature: 0,
      pressure: 0,
      waterLevel: 0,
      motion: 0,
      chlorineLevel: 0,
      turbidity: 0,
      weatherForecast: 'unknown',
      poolBeingCleaned: false,
    };
  }
}

// Control Actuators
function controlActuators(actions) {
  actions.forEach(({ actuator, command, message }) => {
    try {
      switch (actuator) {
        case 'waterFillPump':
          relayWaterIn.write(command ? HIGH : LOW);
          break;
        case 'waterDrainPump':
          relayWaterOut.write(command ? HIGH : LOW);
          break;
        case 'chlorinePump':
          relayChlorinePump.write(command ? HIGH : LOW);
          break;
        case 'filterMotor':
          relayFilterHead.write(command ? HIGH : LOW);
          break;
      }
      console.log(`Actuator ${actuator} set to ${command ? 'ON' : 'OFF'} - ${message}`);
    } catch (error) {
      console.error(`Error controlling actuator ${actuator}:`, error.message);
    }
  });
}

// Log Data to CSV
function logToCSV(sensorData, actions) {
  try {
    const timestamp = new Date().toISOString();
    const actionSummary = actions.map(a => `${a.actuator}:${a.command}`).join('|');
    const logEntry = `${timestamp},${sensorData.pH},${sensorData.temperature},${sensorData.pressure},${sensorData.waterLevel},${sensorData.motion},${actionSummary}\n`;

    fs.appendFileSync(LOG_FILE, logEntry);
    console.log('Logged to CSV:', logEntry.trim());
  } catch (error) {
    console.error('Error writing to log file:', error.message);
  }
}

// Send Sensor Data to Main Server
async function sendSensorData() {
  try {
    const sensorData = readSensorData();
    console.log('Collected Sensor Data:', sensorData);

    const actions = evaluateRules(sensorData, { poolInfo: { minWaterLevel: 30, maxWaterLevel: 80, desiredTemperature: 28 } });
    controlActuators(actions);
    logToCSV(sensorData, actions);

    const res = await axios.post(`${SERVER_URL}/sensor-data`, sensorData, {
      headers: { serialNumber: DEVICE_SERIAL },
    });
    console.log('Server Response:', res.data);

    if (res.data.actions) {
      sendActionsToActuators(res.data.actions);
    }
  } catch (error) {
    console.error('Error in sendSensorData:', error.message);
  }
}

// Graceful Shutdown
function cleanup() {
  console.log('\nCleaning up GPIO pins and exiting...');
  relayWaterIn.write(LOW);
  relayWaterOut.write(LOW);
  relayChlorinePump.write(LOW);
  relayFilterHead.write(LOW);
  process.exit();
}

// Initialize GPIO and Start Monitoring
init(() => {
  console.log('Initializing GPIO Pins...');
  try {
    waterSwitch = new DigitalInput({ pin: 'GPIO17' });
    motionSensor = new DigitalInput({ pin: 'GPIO27' });
    relayWaterIn = new DigitalOutput({ pin: 'GPIO18' });
    relayWaterOut = new DigitalOutput({ pin: 'GPIO23' });
    relayChlorinePump = new DigitalOutput({ pin: 'GPIO24' });
    relayFilterHead = new DigitalOutput({ pin: 'GPIO25' });

    initializeCSV();
    console.log('Sensor Monitoring Initialized. Sending data every 5 seconds...');
    setInterval(sendSensorData, 5000);

    process.on('SIGINT', cleanup); // Handle Ctrl+C
  } catch (error) {
    console.error('Error initializing GPIO:', error.message);
    process.exit(1);
  }
});
