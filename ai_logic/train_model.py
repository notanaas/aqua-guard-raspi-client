import os
import pickle
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report

MODEL_FILE = "ai_logic/trained_model.pkl"
SCALER_FILE = "ai_logic/scaler.pkl"

def train_model(data_file):
    """
    Train a machine learning model using the provided data file.
    :param data_file: Path to the CSV file containing training data
    """
    if not os.path.exists(data_file):
        raise FileNotFoundError(f"Data file not found: {data_file}")

    # Load data
    data = pd.read_csv(data_file)

    # Ensure all non-numeric columns are encoded
    data = pd.get_dummies(data, drop_first=True)

    # Assume the "action" column contains target labels
    features = data.drop("action", axis=1)  # Input features
    labels = data["action"]  # Target labels

    # Split data
    X_train, X_test, y_train, y_test = train_test_split(features, labels, test_size=0.2, random_state=42)

    # Scale data
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    # Train model
    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X_train_scaled, y_train)

    # Evaluate model
    predictions = model.predict(X_test_scaled)
    print("Model Evaluation:")
    print(classification_report(y_test, predictions))

    # Save model and scaler
    with open(MODEL_FILE, "wb") as model_file:
        pickle.dump(model, model_file)
    with open(SCALER_FILE, "wb") as scaler_file:
        pickle.dump(scaler, scaler_file)
    print(f"Model and scaler saved to {MODEL_FILE} and {SCALER_FILE}.")

if __name__ == "__main__":
    train_model("logs/sensor_log.csv")
