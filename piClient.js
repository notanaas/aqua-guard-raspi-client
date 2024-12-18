// Required Modules
const { init } = require('raspi');
const { DigitalInput, DigitalOutput, HIGH, LOW } = require('raspi-gpio');
const I2C = require('raspi-i2c').I2C;
const spi = require('spi-device');
const fs = require('fs');
const path = require('path');
const axios = require('axios');
require('dotenv').config();
const { evaluateRules, sendActionsToActuators } = require('./kbs');

// Environment Variables
const PRIMARY_SERVER = process.env.PRIMARY_SERVER || 'http://192.168.1.15:3001';
const BACKUP_SERVER = process.env.BACKUP_SERVER || 'http://localhost:3001';
const DEVICE_SERIAL = process.env.DEVICE_SERIAL || 'UNKNOWN_SERIAL';
const DEVICE_PASSWORD = process.env.DEVICE_PASSWORD || 'default_password';
const LOGIN_ENDPOINT = `${PRIMARY_SERVER}/api/auth/login`;
const REFRESH_ENDPOINT = `${PRIMARY_SERVER}/api/auth/refresh-token`;
const LOG_FILE = path.join(__dirname, 'logs', 'sensor_actions_log.csv');

// In-memory Token Storage
let accessToken = null;
let refreshToken = null;

// GPIO Pin Assignments
let waterSwitch, motionSensor;
let relayWaterIn, relayWaterOut, relayChlorinePump, relayFilterHead;


// I2C Configuration for UV Sensor
const i2c = new I2C();
const UV_SENSOR_ADDR = 0x38; // CJMCU-6070 I2C address

// Initialize CSV Logging
function initializeCSV() {
  const logDir = path.dirname(LOG_FILE);
  if (!fs.existsSync(logDir)) fs.mkdirSync(logDir, { recursive: true });
  if (!fs.existsSync(LOG_FILE)) {
    fs.writeFileSync(LOG_FILE, 'Timestamp,pH,Temperature,Pressure,Current,WaterLevel,UV,Motion,Actions\n');
    console.log('Created log file:', LOG_FILE);
  }
}

// Token Management
async function fetchAuthToken() {
  try {
    console.log('Fetching auth token...');
    const response = await axios.post(LOGIN_ENDPOINT, { loginIdentifier: DEVICE_SERIAL, password: DEVICE_PASSWORD });
    accessToken = response.data.accessToken;
    refreshToken = response.data.refreshToken;
    console.log('Successfully fetched auth token.');
  } catch (error) {
    console.error('Error fetching auth token:', error.message);
    accessToken = null;
  }
}

// Sensor Data Reading
function readUVSensor() {
  try {
    const uvData = i2c.readByteSync(UV_SENSOR_ADDR, 0x00); // Read UV intensity
    return uvData / 256; // Normalize data (example scaling)
  } catch (err) {
    console.error('Error reading UV sensor:', err.message);
    return 0;
  }
}

function readADC(channel) {
  try {
    const command = Buffer.from([0xC0 | ((channel & 0x03) << 4), 0x00]); // Command to select channel
    const response = spi.transfer(command);
    const adcValue = ((response[0] & 0x03) << 8) | response[1];
    return (adcValue * 3.3) / 1023; // Convert to voltage
  } catch (err) {
    console.error(`Error reading ADC channel ${channel}:`, err.message);
    return 0;
  }
}

function readSensorData() {
  return {
    pH: readADC(0), // CH0
    temperature: readADC(1), // CH1
    pressure: readADC(2), // CH2
    current: readADC(3), // CH3
    waterLevel: waterSwitch.read() === HIGH ? 100 : 0,
    uvIntensity: readUVSensor(),
    motion: motionSensor.read() === HIGH ? 1 : 0,
  };
}

// Control Actuators
function controlActuators(actions) {
  actions.forEach(({ actuator, command }) => {
    try {
      switch (actuator) {
        case 'waterFillPump': relayWaterIn.write(command ? HIGH : LOW); break;
        case 'waterDrainPump': relayWaterOut.write(command ? HIGH : LOW); break;
        case 'chlorinePump': relayChlorinePump.write(command ? HIGH : LOW); break;
        case 'filterMotor': relayFilterHead.write(command ? HIGH : LOW); break;
      }
      console.log(`Actuator ${actuator} set to ${command ? 'ON' : 'OFF'}`);
    } catch (error) {
      console.error(`Error controlling actuator ${actuator}:`, error.message);
    }
  });
}

// Log Data to CSV
function logToCSV(sensorData, actions) {
  const timestamp = new Date().toISOString();
  const actionSummary = actions.map(a => `${a.actuator}:${a.command}`).join('|');
  const logEntry = `${timestamp},${sensorData.pH},${sensorData.temperature},${sensorData.pressure},${sensorData.current},${sensorData.waterLevel},${sensorData.uvIntensity},${sensorData.motion},${actionSummary}\n`;
  fs.appendFileSync(LOG_FILE, logEntry);
}

// Send Data to Server
async function sendSensorData() {
  const sensorData = readSensorData();
  console.log('Collected Sensor Data:', sensorData);

  try {
    const response = await axios.post(`${PRIMARY_SERVER}/api/devices/sensor-data`, sensorData, {
      headers: { Authorization: `Bearer ${accessToken}`, serialNumber: DEVICE_SERIAL },
    });
    controlActuators(response.data.actions);
    logToCSV(sensorData, response.data.actions);
  } catch (error) {
    console.error('Error sending data to server:', error.message);
  }
}

// Cleanup GPIO
function cleanup() {
  console.log('Cleaning up GPIO pins...');
  relayWaterIn?.write(LOW);
  relayWaterOut?.write(LOW);
  relayChlorinePump?.write(LOW);
  relayFilterHead?.write(LOW);
  process.exit();
}

// Initialize System
init(async () => {
  console.log('Initializing GPIO and sensors...');
  try {
    const spiDevice = spi.open(0, 0, (err) => {
      if (err) {
        console.error('Error opening SPI device:', err.message);
      } else {
        console.log('SPI device opened successfully');
      }
    });

    waterSwitch = new DigitalInput({ pin: 'GPIO17' });
    motionSensor = new DigitalInput({ pin: 'GPIO27' });
    relayWaterIn = new DigitalOutput({ pin: 'GPIO18' });
    relayWaterOut = new DigitalOutput({ pin: 'GPIO23' });
    relayChlorinePump = new DigitalOutput({ pin: 'GPIO24' });
    relayFilterHead = new DigitalOutput({ pin: 'GPIO25' });

    initializeCSV();
    await fetchAuthToken();
    console.log('System initialized. Starting data collection...');
    setInterval(sendSensorData, 5000);

    process.on('SIGINT', cleanup);
    process.on('SIGTERM', cleanup);
  } catch (error) {
    console.error('Initialization error:', error.message);
    cleanup();
  }
});