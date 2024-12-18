import requests
from datetime import datetime


def evaluate_rules(sensor_data, device):
    actions = []

    # Rule 1: pH Level Adjustment (pH should be between 7.2 and 7.8)
    if sensor_data["pH"] < 7.2:
        actions.append({
            "actuator": "chlorinePump",
            "command": True,  # Turn on the chlorine pump to raise pH
            "message": f"pH is low (Current: {sensor_data['pH']}), activating chlorine pump to increase pH."
        })
    elif sensor_data["pH"] > 7.8:
        actions.append({
            "actuator": "chlorinePump",
            "command": False,  # Turn off the chlorine pump to lower pH
            "message": f"pH is high (Current: {sensor_data['pH']}), deactivating chlorine pump to lower pH."
        })

    # Rule 2: Chlorine Level Adjustment (Chlorine level should be between 1-3 ppm)
    if sensor_data["chlorineLevel"] < 1:
        actions.append({
            "actuator": "chlorinePump",
            "command": True,
            "message": f"Chlorine level is low (Current: {sensor_data['chlorineLevel']} ppm), activating chlorine pump."
        })
    elif sensor_data["chlorineLevel"] > 3:
        actions.append({
            "actuator": "chlorinePump",
            "command": False,
            "message": f"Chlorine level is high (Current: {sensor_data['chlorineLevel']} ppm), deactivating chlorine pump."
        })

    # Rule 3: Turbidity (Filtration and Vacuum)
    if sensor_data["turbidity"] > 50:  # 50 NTU (example threshold)
        actions.append({
            "actuator": "poolFilter",
            "command": True,
            "message": f"Water turbidity is high (Current: {sensor_data['turbidity']} NTU), running pool filter."
        })
        actions.append({
            "actuator": "poolVacuum",
            "command": True,
            "message": f"Water turbidity is high (Current: {sensor_data['turbidity']} NTU), activating pool vacuum."
        })

    # Rule 4: Water Level Adjustment
    if sensor_data["waterLevel"] < device["poolInfo"]["minWaterLevel"]:
        actions.append({
            "actuator": "waterFillPump",
            "command": True,
            "message": f"Water level is low (Current: {sensor_data['waterLevel']}), activating water fill pump."
        })
    elif sensor_data["waterLevel"] > device["poolInfo"]["maxWaterLevel"]:
        actions.append({
            "actuator": "waterDrainPump",
            "command": True,
            "message": f"Water level is high (Current: {sensor_data['waterLevel']}), activating water drainage pump."
        })

    # Rule 5: Temperature Regulation
    if sensor_data["temperature"] < device["poolInfo"]["desiredTemperature"]:
        actions.append({
            "actuator": "poolHeater",
            "command": True,
            "message": f"Water temperature is low (Current: {sensor_data['temperature']}), activating pool heater."
        })
    elif sensor_data["temperature"] > device["poolInfo"]["desiredTemperature"] + 2:
        actions.append({
            "actuator": "poolHeater",
            "command": False,
            "message": f"Water temperature is high (Current: {sensor_data['temperature']}), deactivating pool heater."
        })

    # Rule 6: Pool Cover
    current_time = datetime.now().hour
    is_night = current_time >= 18 or current_time <= 6
    if is_night or sensor_data["weatherForecast"] == "rainy" or sensor_data["temperature"] < 15:
        actions.append({
            "actuator": "poolCover",
            "command": True,
            "message": "Pool cover activated due to night time or weather conditions."
        })
    else:
        actions.append({
            "actuator": "poolCover",
            "command": False,
            "message": "Pool cover deactivated, conditions are favorable."
        })

    # Rule 7: LED Lights
    if is_night or sensor_data.get("poolBeingCleaned", False):
        actions.append({
            "actuator": "ledLights",
            "command": True,
            "message": "It's night time or the pool is being cleaned, activating LED lights."
        })

    return actions


def send_actions_to_actuators(actions):
    for action in actions:
        try:
            # Send the action to the actuator via API
            response = requests.post(
                "http://actuator-endpoint.com/trigger",
                json={
                    "actuator": action["actuator"],
                    "command": action["command"],
                    "message": action["message"]
                }
            )
            response.raise_for_status()
            print(f"Action sent successfully: {action}")
        except requests.RequestException as e:
            print(f"Error sending action {action['actuator']}: {e}")
