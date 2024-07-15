import time


class BESS:
    def __init__(
        self,
        id,
        name,
        capacity,
        charge_level=0,
        switch_status=False,
        device_status="offline",
    ):
        self.id = id
        self.name = name
        self.capacity = capacity
        self.charge_level = charge_level
        self.switch_status = switch_status
        self.device_status = device_status
        self.is_valid = False

    @staticmethod
    def validate_data(data):
        required_keys = [
            "id",
            "name",
            "capacity",
            "charge_level",
            "switch_status",
            "device_status",
        ]
        for key in required_keys:
            if key not in data:
                print(f"Missing key: {key} in data: {data}")
                return False
        if not isinstance(data["id"], int) or data["id"] <= 0:
            print(f"Invalid id: {data['id']}")
            return False
        if not isinstance(data["name"], str) or not data["name"]:
            print(f"Invalid name: {data['name']}")
            return False
        if not isinstance(data["capacity"], (int, float)) or data["capacity"] <= 0:
            print(f"Invalid capacity: {data['capacity']}")
            return False
        if (
            not isinstance(data["charge_level"], (int, float))
            or data["charge_level"] < 0
        ):
            print(f"Invalid charge_level: {data['charge_level']}")
            return False
        if not isinstance(data["switch_status"], bool):
            print(f"Invalid switch_status: {data['switch_status']}")
            return False
        if data["device_status"] not in ["online", "offline"]:
            print(f"Invalid device_status: {data['device_status']}")
            return False
        return True

    @classmethod
    def create_instance(cls, data):
        if cls.validate_data(data):
            instance = cls(**data)
            instance.is_valid = True
            return instance
        return None

    def activate(self):
        self.device_status = "online"
        self.switch_status = True
        print(f"{self.name} is now active with switch_status = {self.switch_status}.")

    def deactivate(self):
        self.device_status = "offline"
        self.switch_status = False
        print(f"{self.name} is now inactive with switch_status = {self.switch_status}.")

    def charge(self, percent):
        charge_amount = self.capacity * (percent / 100)
        new_charge_level = self.charge_level + charge_amount
        if new_charge_level > self.capacity:
            print(f"{self.name} charged to its maximum capacity: {self.capacity} kWh")
            new_charge_level = self.capacity
        self.charge_level = new_charge_level
        print(f"{self.name} charged by {percent}% to {self.charge_level} kWh")
        return percent, charge_amount

    def discharge(self, percent):
        discharge_amount = self.capacity * (percent / 100)
        new_charge_level = self.charge_level - discharge_amount
        if new_charge_level < 0:
            print(f"{self.name} discharged to 0 kWh")
            new_charge_level = 0
        self.charge_level = new_charge_level
        print(f"{self.name} discharged by {percent}% to {self.charge_level} kWh")
        return percent, discharge_amount

    def get_charge_level(self):
        return self.charge_level

    def get_capacity(self):
        return self.capacity

    def get_status(self):
        return self.device_status

    def get_switch_status(self):
        return self.switch_status

    def is_uncharged(self):
        return self.charge_level < self.capacity

    def try_activate(self, attempts=3, delay=1):
        for attempt in range(attempts):
            self.activate()
            time.sleep(delay)
            if self.device_status == "online":
                print(f"{self.name} activated successfully on attempt {attempt + 1}.")
                return True
            print(f"Attempt {attempt + 1} to activate {self.name} failed.")
        print(f"Failed to activate {self.name} after {attempts} attempts.")
        return False

    def try_deactivate(self, attempts=3, delay=1):
        for attempt in range(attempts):
            self.deactivate()
            time.sleep(delay)
            if self.device_status == "offline":
                print(f"{self.name} deactivated successfully on attempt {attempt + 1}.")
                return True
            print(f"Attempt {attempt + 1} to deactivate {self.name} failed.")
        print(f"Failed to deactivate {self.name} after {attempts} attempts.")
        return False

    def try_charge(self, percent, attempts=3, delay=1):
        for attempt in range(attempts):
            percent_charged, amount_charged = self.charge(percent)
            time.sleep(delay)
            if self.charge_level == self.charge_level:
                print(f"{self.name} charged successfully on attempt {attempt + 1}.")
                return percent_charged, amount_charged
            print(f"Attempt {attempt + 1} to charge {self.name} failed.")
        print(f"Failed to charge {self.name} after {attempts} attempts.")
        return None

    def try_discharge(self, percent, attempts=3, delay=1):
        for attempt in range(attempts):
            percent_discharged, amount_discharged = self.discharge(percent)
            time.sleep(delay)
            if self.charge_level == self.charge_level:
                print(f"{self.name} discharged successfully on attempt {attempt + 1}.")
                return percent_discharged, amount_discharged
            print(f"Attempt {attempt + 1} to discharge {self.name} failed.")
        print(f"Failed to discharge {self.name} after {attempts} attempts.")
        return None
