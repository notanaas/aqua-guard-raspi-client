const axios = require('axios');

// Helper function to evaluate if the pool needs cleaning or other actions
const evaluateRules = (sensorData, device) => {
    const actions = [];

    // Rule 1: pH Level Adjustment (pH should be between 7.2 and 7.8)
    if (sensorData.pH < 7.2) {
        actions.push({
            actuator: 'chlorinePump',
            command: true, // Turn on the chlorine pump to raise pH
            message: `pH is low (Current: ${sensorData.pH}), activating chlorine pump to increase pH.`,
        });
    } else if (sensorData.pH > 7.8) {
        actions.push({
            actuator: 'chlorinePump',
            command: false, // Turn off the chlorine pump to lower pH
            message: `pH is high (Current: ${sensorData.pH}), deactivating chlorine pump to lower pH.`,
        });
    }

    // Rule 2: Chlorine Level Adjustment (Chlorine level should be between 1-3 ppm)
    if (sensorData.chlorineLevel < 1) {
        actions.push({
            actuator: 'chlorinePump',
            command: true, // Activate chlorine pump to raise chlorine level
            message: `Chlorine level is low (Current: ${sensorData.chlorineLevel} ppm), activating chlorine pump to raise chlorine.`,
        });
    } else if (sensorData.chlorineLevel > 3) {
        actions.push({
            actuator: 'chlorinePump',
            command: false, // Deactivate chlorine pump to prevent over-chlorination
            message: `Chlorine level is high (Current: ${sensorData.chlorineLevel} ppm), deactivating chlorine pump.`,
        });
    }

    // Rule 3: Turbidity (Filtration and Vacuum)
    // If turbidity is too high, clean the pool by running the filter and vacuum
    if (sensorData.turbidity > 50) {  // 50 NTU (example threshold)
        actions.push({
            actuator: 'poolFilter',
            command: true, // Run the pool filter
            message: `Water turbidity is high (Current: ${sensorData.turbidity} NTU), running pool filter.`,
        });
        actions.push({
            actuator: 'poolVacuum',
            command: true, // Run the pool vacuum
            message: `Water turbidity is high (Current: ${sensorData.turbidity} NTU), activating pool vacuum.`,
        });
    }

    // Rule 4: Water Level Adjustment
    // If the water level is too low, trigger the fill pump
    if (sensorData.waterLevel < device.poolInfo.minWaterLevel) {
        actions.push({
            actuator: 'waterFillPump',
            command: true, // Turn on water fill pump
            message: `Water level is low (Current: ${sensorData.waterLevel}), activating water fill pump.`,
        });
    }
    // If the water level is too high, trigger the drainage pump
    else if (sensorData.waterLevel > device.poolInfo.maxWaterLevel) {
        actions.push({
            actuator: 'waterDrainPump',
            command: true, // Turn on water drainage pump
            message: `Water level is high (Current: ${sensorData.waterLevel}), activating water drainage pump.`,
        });
    }

    // Rule 5: Temperature Regulation (Adjust pool heater if necessary)
    if (sensorData.temperature < device.poolInfo.desiredTemperature) {
        actions.push({
            actuator: 'poolHeater',
            command: true, // Activate pool heater
            message: `Water temperature is low (Current: ${sensorData.temperature}), activating pool heater.`,
        });
    } else if (sensorData.temperature > device.poolInfo.desiredTemperature + 2) {
        actions.push({
            actuator: 'poolHeater',
            command: false, // Deactivate pool heater
            message: `Water temperature is high (Current: ${sensorData.temperature}), deactivating pool heater.`,
        });
    }

    // Rule 6: Pool Cover (Activate if it's night or rainy, or if temperature is low)
    const currentTime = new Date().getHours();
    const isNight = currentTime >= 18 || currentTime <= 6;
    if (isNight || sensorData.weatherForecast === 'rainy' || sensorData.temperature < 15) {
        actions.push({
            actuator: 'poolCover',
            command: true, // Cover the pool
            message: `Pool cover activated due to night time or weather conditions.`,
        });
    } else {
        actions.push({
            actuator: 'poolCover',
            command: false, // Open the pool cover
            message: `Pool cover deactivated, conditions are favorable.`,
        });
    }

    // Rule 7: LED Lights (Activate if it's night or pool is being cleaned)
    if (isNight || sensorData.poolBeingCleaned) {
        actions.push({
            actuator: 'ledLights',
            command: true, // Turn on LED lights
            message: `It's night time or the pool is being cleaned, activating LED lights.`,
        });
    }

    return actions;
};

// Example function to send the actions to the actuators
const sendActionsToActuators = async (actions) => {
    for (let action of actions) {
        try {
            // Send the action to the actuator via API (for example, via axios)
            await axios.post('http://actuator-endpoint.com/trigger', {
                actuator: action.actuator,
                command: action.command,
                message: action.message,
            });
        } catch (error) {
            console.error(`Error sending action ${action.actuator}:`, error);
        }
    }
};

module.exports = { evaluateRules, sendActionsToActuators };
