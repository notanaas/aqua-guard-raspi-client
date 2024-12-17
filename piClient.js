const { init } = require('raspi');
const { DigitalInput, DigitalOutput, HIGH, LOW } = require('raspi-gpio');
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
    const response = await axios.post(REFRESH_ENDPOINT, {
      refreshToken,
    });

    accessToken = response.data.accessToken;
    console.log('Access token refreshed.');
  } catch (error) {
    console.error('Error refreshing access token:', error.message);
    accessToken = null; // Force re-login
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
      headers: {
        Authorization: `Bearer ${accessToken}`,
        serialNumber: DEVICE_SERIAL,
      },
    });
    console.log(`Data sent to ${serverUrl}:`, response.data);
    return response.data;
  } catch (error) {
    if (error.response && error.response.status === 401) {
      console.warn('Token expired. Attempting to refresh...');
      await refreshAccessToken();
      if (accessToken) {
        return sendToServer(sensorData, serverUrl); // Retry with refreshed token
      }
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
    waterLevel: waterSwitch.read() === HIGH ? 100 : 0,
    motion: motionSensor.read() === HIGH ? 1 : 0,
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

function cleanup() {
  console.log('Cleaning up GPIO pins and exiting...');
  relayWaterIn.write(LOW);
  relayWaterOut.write(LOW);
  relayChlorinePump.write(LOW);
  relayFilterHead.write(LOW);

  process.exit();
}
process.on('SIGINT', cleanup); // Catch Ctrl+C
process.on('SIGTERM', cleanup); // Catch termination signals

// Initialize GPIO and Start Monitoring
let waterSwitch, motionSensor, relayWaterIn, relayWaterOut, relayChlorinePump, relayFilterHead;

init(async () => {
  console.log('Initializing GPIO Pins...');
  try {
    waterSwitch = new DigitalInput({ pin: 'GPIO17' });
    motionSensor = new DigitalInput({ pin: 'GPIO27' });
    relayWaterIn = new DigitalOutput({ pin: 'GPIO18' });
    relayWaterOut = new DigitalOutput({ pin: 'GPIO23' });
    relayChlorinePump = new DigitalOutput({ pin: 'GPIO24' });
    relayFilterHead = new DigitalOutput({ pin: 'GPIO25' });

    initializeCSV();
    console.log('Fetching initial auth token...');
    await fetchAuthToken();

    console.log('Monitoring initialized. Sending data every 5 seconds...');
    setInterval(sendSensorData, 5000);

    process.on('SIGINT', cleanup);
  } catch (error) {
    console.error('Error initializing GPIO:', error.message);
    process.exit(1);
  }
});
