const pigpio = require('pigpio');
const { Gpio } = pigpio; // Import Gpio class
const axios = require('axios');
const fs = require('fs');
const path = require('path');
require('dotenv').config();
const { evaluateRules, sendActionsToActuators } = require('./kbs');

// Environment Variables
const PRIMARY_SERVER = process.env.PRIMARY_SERVER || 'http://192.168.1.15:3001';
const BACKUP_SERVER = process.env.BACKUP_SERVER || 'http://localhost:3001';
const DEVICE_SERIAL = process.env.DEVICE_SERIAL || 'UNKNOWN_SERIAL';
const DEVICE_PASSWORD = process.env.DEVICE_PASSWORD || 'default_password';
const LOGIN_ENDPOINT = process.env.LOGIN_ENDPOINT || `${PRIMARY_SERVER}/api/auth/login`;
const REFRESH_ENDPOINT = process.env.REFRESH_ENDPOINT || `${PRIMARY_SERVER}/api/auth/refresh-token`;
const LOG_FILE = path.join(__dirname, 'logs', 'sensor_actions_log.csv');

// In-memory Token Storage
let accessToken = null;
let refreshToken = null;

// GPIO Initialization
let waterSwitch, motionSensor, relayWaterIn, relayWaterOut, relayChlorinePump, relayFilterHead;

// Initialize CSV Logging
function initializeCSV() {
  if (!fs.existsSync(LOG_FILE)) {
    fs.writeFileSync(LOG_FILE, 'Timestamp,pH,Temperature,Pressure,WaterLevel,Motion,Actions\n');
    console.log('Created log file:', LOG_FILE);
  }
}

// Token Management
async function fetchAuthToken() {
  try {
    console.log('Fetching auth token...');
    const response = await axios.post(LOGIN_ENDPOINT, {
      loginIdentifier: DEVICE_SERIAL,
      password: DEVICE_PASSWORD,
    });

    accessToken = response.data.accessToken; // Get access token
    refreshToken = response.data.refreshToken; // Get refresh token
    console.log('Successfully fetched access token.');
  } catch (error) {
    console.error('Error fetching auth token:', error.message);
    accessToken = null;
  }
}

async function refreshAccessToken() {
  try {
    console.log('Refreshing access token...');
    const response = await axios.post(REFRESH_ENDPOINT, { refreshToken });
    accessToken = response.data.accessToken;
    console.log('Access token refreshed.');
  } catch (error) {
    console.error('Error refreshing access token:', error.message);
    accessToken = null;
  }
}

// Send Sensor Data to Server
async function sendToServer(sensorData, serverUrl) {
  if (!accessToken) {
    await fetchAuthToken();
    if (!accessToken) {
      console.error('Failed to retrieve access token. Aborting request.');
      return null;
    }
  }

  try {
    const response = await axios.post(`${serverUrl}/api/devices/sensor-data`, sensorData, {
      headers: { Authorization: `Bearer ${accessToken}`, serialNumber: DEVICE_SERIAL },
    });
    console.log(`Data sent to ${serverUrl}:`, response.data);
    return response.data;
  } catch (error) {
    if (error.response && error.response.status === 401) {
      console.warn('Token expired. Attempting to refresh...');
      await refreshAccessToken();
      if (accessToken) return sendToServer(sensorData, serverUrl);
    }
    console.error(`Error sending data to ${serverUrl}:`, error.message);
    return null;
  }
}

// Control Actuators
function controlActuators(actions) {
  actions.forEach(({ actuator, command }) => {
    try {
      switch (actuator) {
        case 'waterFillPump':
          relayWaterIn.digitalWrite(command ? 1 : 0);
          break;
        case 'waterDrainPump':
          relayWaterOut.digitalWrite(command ? 1 : 0);
          break;
        case 'chlorinePump':
          relayChlorinePump.digitalWrite(command ? 1 : 0);
          break;
        case 'filterMotor':
          relayFilterHead.digitalWrite(command ? 1 : 0);
          break;
      }
      console.log(`Actuator ${actuator} set to ${command ? 'ON' : 'OFF'}`);
    } catch (error) {
      console.error(`Error controlling actuator ${actuator}:`, error.message);
    }
  });
}

// Simulated Sensor Data
function readSensorData() {
  return {
    pH: (Math.random() * 14).toFixed(2),
    temperature: (20 + Math.random() * 10).toFixed(2),
    pressure: (Math.random() * 100).toFixed(2),
    waterLevel: waterSwitch.digitalRead() ? 100 : 0,
    motion: motionSensor.digitalRead() ? 1 : 0,
  };
}

// Log Data to CSV
function logToCSV(sensorData, actions) {
  const timestamp = new Date().toISOString();
  const actionSummary = actions.map(a => `${a.actuator}:${a.command}`).join('|');
  const logEntry = `${timestamp},${sensorData.pH},${sensorData.temperature},${sensorData.pressure},${sensorData.waterLevel},${sensorData.motion},${actionSummary}\n`;
  fs.appendFileSync(LOG_FILE, logEntry);
  console.log('Logged to CSV:', logEntry.trim());
}

// Send Sensor Data
async function sendSensorData() {
  const sensorData = readSensorData();
  console.log('Collected Sensor Data:', sensorData);

  let serverResponse = await sendToServer(sensorData, PRIMARY_SERVER);
  if (!serverResponse) {
    console.warn('Switching to backup server...');
    serverResponse = await sendToServer(sensorData, BACKUP_SERVER);
  }

  if (serverResponse && serverResponse.actions) {
    controlActuators(serverResponse.actions);
    logToCSV(sensorData, serverResponse.actions);
  } else {
    console.error('Failed to send data to both servers.');
  }
}

// Cleanup Function
function cleanup() {
  console.log('Cleaning up GPIO pins and exiting...');
  relayWaterIn.digitalWrite(0);
  relayWaterOut.digitalWrite(0);
  relayChlorinePump.digitalWrite(0);
  relayFilterHead.digitalWrite(0);
  process.exit();
}

// Initialize GPIO and Start Monitoring
function initializeGPIO() {
  console.log('Initializing GPIO Pins...');
  waterSwitch = new Gpio(17, { mode: Gpio.INPUT, pullUpDown: Gpio.PUD_UP });
  motionSensor = new Gpio(27, { mode: Gpio.INPUT, pullUpDown: Gpio.PUD_UP });
  relayWaterIn = new Gpio(18, { mode: Gpio.OUTPUT });
  relayWaterOut = new Gpio(23, { mode: Gpio.OUTPUT });
  relayChlorinePump = new Gpio(24, { mode: Gpio.OUTPUT });
  relayFilterHead = new Gpio(25, { mode: Gpio.OUTPUT });
}

// Start the Application
(async () => {
  try {
    initializeCSV();
    initializeGPIO();
    console.log('Fetching initial auth token...');
    await fetchAuthToken();

    console.log('Monitoring initialized. Sending data every 5 seconds...');
    setInterval(sendSensorData, 5000);

    process.on('SIGINT', cleanup); // Catch Ctrl+C
    process.on('SIGTERM', cleanup); // Catch termination signals
  } catch (error) {
    console.error('Error during initialization:', error.message);
    cleanup();
  }
})();
