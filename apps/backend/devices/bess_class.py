import time


class BESS:
    def __init__(
        self, id, name, capacity, charge_level=0, switch_status=False, status="offline"
    ):
        self.id = id
        self.name = name
        self.capacity = capacity
        self.charge_level = charge_level
        self.switch_status = switch_status
        self.status = status
        self.is_valid = False

    @staticmethod
    def validate_data(data):
        required_keys = [
            "id",
            "name",
            "capacity",
            "charge_level",
            "switch_status",
            "status",
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
        if data["status"] not in ["online", "offline"]:
            print(f"Invalid status: {data['status']}")
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
        self.status = "online"
        self.switch_status = True
        print(f"{self.name} is now active with switch_status = {self.switch_status}.")

    def deactivate(self):
        self.status = "offline"
        self.switch_status = False
        print(f"{self.name} is now inactive with switch_status = {self.switch_status}.")

    def charge(self, amount):
        if self.charge_level + amount > self.capacity:
            print(f"{self.name} charged to its maximum capacity: {self.capacity} kWh")
            self.charge_level = self.capacity
        else:
            print(f"{self.name} charged by {amount} kWh")
            self.charge_level += amount

    def discharge(self, amount):
        if self.charge_level - amount < 0:
            print(f"{self.name} discharged to 0 kWh")
            self.charge_level = 0
        else:
            print(f"{self.name} discharged by {amount} kWh")
            self.charge_level -= amount

    def get_charge_level(self):
        return self.charge_level

    def get_capacity(self):
        return self.capacity

    def get_status(self):
        return self.status

    def get_switch_status(self):
        return self.switch_status

    def try_activate(self, attempts=3, delay=1):
        for attempt in range(attempts):
            try:
                self.activate()
                print(f"{self.name} activated successfully on attempt {attempt + 1}.")
                return True
            except Exception as e:
                print(f"Attempt {attempt + 1} to activate {self.name} failed: {e}")
                time.sleep(delay)
        print(f"Failed to activate {self.name} after {attempts} attempts.")
        return False

    def try_deactivate(self, attempts=3, delay=1):
        for attempt in range(attempts):
            try:
                self.deactivate()
                print(f"{self.name} deactivated successfully on attempt {attempt + 1}.")
                return True
            except Exception as e:
                print(f"Attempt {attempt + 1} to deactivate {self.name} failed: {e}")
                time.sleep(delay)
        print(f"Failed to deactivate {self.name} after {attempts} attempts.")
        return False

    def try_charge(self, amount, attempts=3, delay=1):
        for attempt in range(attempts):
            try:
                self.charge(amount)
                print(f"{self.name} charged successfully on attempt {attempt + 1}.")
                return True
            except Exception as e:
                print(f"Attempt {attempt + 1} to charge {self.name} failed: {e}")
                time.sleep(delay)
        print(f"Failed to charge {self.name} after {attempts} attempts.")
        return False

    def try_discharge(self, amount, attempts=3, delay=1):
        for attempt in range(attempts):
            try:
                self.discharge(amount)
                print(f"{self.name} discharged successfully on attempt {attempt + 1}.")
                return True
            except Exception as e:
                print(f"Attempt {attempt + 1} to discharge {self.name} failed: {e}")
                time.sleep(delay)
        print(f"Failed to discharge {self.name} after {attempts} attempts.")
        return False
