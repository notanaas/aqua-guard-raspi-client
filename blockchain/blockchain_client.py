from web3 import Web3

class BlockchainClient:
    def __init__(self, blockchain_url, contract_address, contract_abi, serial_number):
        self.web3 = Web3(Web3.HTTPProvider(blockchain_url))
        self.contract = self.web3.eth.contract(address=contract_address, abi=contract_abi)
        self.account = self.web3.eth.accounts[0]
        self.serial_number = serial_number

    def log_sensor_data(self, sensor_data):
        try:
            for sensor, value in sensor_data.items():
                tx_hash = self.contract.functions.addSensorData(
                    self.serial_number,
                    sensor,
                    str(value)
                ).transact({'from': self.account})
                self.web3.eth.wait_for_transaction_receipt(tx_hash)
            print("Sensor data logged to blockchain.")
        except Exception as e:
            print(f"Error logging sensor data to blockchain: {e}")
