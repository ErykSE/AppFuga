import time


class EnergySource:
    def __init__(
        self,
        id,
        name,
        max_output,
        current_output=0,
        switch_status=False,
        status="offline",
    ):
        self.id = id
        self.name = name
        self.max_output = max_output
        self.current_output = current_output
        self.switch_status = switch_status
        self.status = status
        self.is_valid = False

    @staticmethod
    def validate_data(data):
        required_keys = [
            "id",
            "name",
            "max_output",
            "current_output",
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
        if not isinstance(data["max_output"], (int, float)) or data["max_output"] <= 0:
            print(f"Invalid max_output: {data['max_output']}")
            return False
        if (
            not isinstance(data["current_output"], (int, float))
            or data["current_output"] < 0
        ):
            print(f"Invalid current_output: {data['current_output']}")
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

    def activate(self, desired_output=None):
        self.status = "online"
        self.switch_status = True
        if desired_output is not None:
            self.set_output(desired_output)
        print(f"{self.name} is now active with switch_status = {self.switch_status}.")

    def deactivate(self):
        self.status = "offline"
        self.current_output = 0
        self.switch_status = False
        print(f"{self.name} is now inactive with switch_status = {self.switch_status}.")

    def increase_output(self, amount):
        if self.status != "online":
            print(f"{self.name} is not active.")
            return

        if self.current_output + amount > self.max_output:
            print(f"{self.name} output increased to its maximum: {self.max_output} kW")
            self.current_output = self.max_output
        else:
            print(f"{self.name} output increased by {amount} kW")
            self.current_output += amount

    def decrease_output(self, amount):
        if self.status != "online":
            print(f"{self.name} is not active.")
            return

        if self.current_output - amount < 0:
            print(f"{self.name} output decreased to 0 kW")
            self.current_output = 0
        else:
            print(f"{self.name} output decreased by {amount} kW")
            self.current_output -= amount

    def set_output(self, amount):
        if amount > self.max_output:
            print(f"{self.name} output set to its maximum: {self.max_output} kW")
            self.current_output = self.max_output
        else:
            print(f"{self.name} output set to {amount} kW")
            self.current_output = amount

    def get_current_output(self):
        return self.current_output

    def get_max_output(self):
        return self.max_output

    def get_status(self):
        return self.status

    def get_switch_status(self):
        return self.switch_status

    def try_activate(self, attempts=3, delay=1, desired_output=None):
        for attempt in range(attempts):
            try:
                self.activate(desired_output)
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

    def try_increase_output(self, amount, attempts=3, delay=1):
        for attempt in range(attempts):
            try:
                self.increase_output(amount)
                print(
                    f"{self.name} output increased successfully on attempt {attempt + 1}."
                )
                return True
            except Exception as e:
                print(
                    f"Attempt {attempt + 1} to increase output of {self.name} failed: {e}"
                )
                time.sleep(delay)
        print(f"Failed to increase output of {self.name} after {attempts} attempts.")
        return False

    def try_decrease_output(self, amount, attempts=3, delay=1):
        for attempt in range(attempts):
            try:
                self.decrease_output(amount)
                print(
                    f"{self.name} output decreased successfully on attempt {attempt + 1}."
                )
                return True
            except Exception as e:
                print(
                    f"Attempt {attempt + 1} to decrease output of {self.name} failed: {e}"
                )
                time.sleep(delay)
        print(f"Failed to decrease output of {self.name} after {attempts} attempts.")
        return False
