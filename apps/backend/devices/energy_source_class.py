import time


class EnergySource:
    def __init__(
        self,
        id,
        name,
        priority,
        max_output,
        min_output,
        actual_output,
        switch_status,
        device_status,
    ):
        self.id = id
        self.name = name
        self.priority = priority
        self.max_output = max_output
        self.min_output = min_output
        self.actual_output = actual_output
        self.switch_status = switch_status
        self.device_status = device_status
        self.is_valid = False

    @staticmethod
    def validate_data(data):
        required_keys = [
            "id",
            "name",
            "priority",
            "max_output",
            "min_output",
            "actual_output",
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
        if not isinstance(data["priority"], int) or data["priority"] < 0:
            print(f"Invalid priority: {data['priority']}")
            return False
        if not isinstance(data["max_output"], (int, float)) or data["max_output"] <= 0:
            print(f"Invalid max_output: {data['max_output']}")
            return False
        if not isinstance(data["min_output"], (int, float)) or data["min_output"] < 0:
            print(f"Invalid min_output: {data['min_output']}")
            return False
        if data["min_output"] > data["max_output"]:
            print(
                f"min_output ({data['min_output']}) is greater than max_output ({data['max_output']})"
            )
            return False
        if (
            not isinstance(data["actual_output"], (int, float))
            or data["actual_output"] > data["max_output"]
            or data["actual_output"] < data["min_output"]
        ):
            print(f"Invalid actual_output: {data['actual_output']}")
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

    def get_actual_output(self):
        return self.actual_output

    def get_max_output(self):
        return self.max_output

    def get_min_output(self):
        return self.min_output

    def get_status(self):
        return self.device_status

    def get_switch_status(self):
        return self.switch_status

    def get_name(self):
        return self.name

    def is_at_max_output(self):
        return self.actual_output >= self.max_output

    def get_available_capacity(self):
        return self.max_output - self.actual_output

    def activate(self):
        self.device_status = "online"
        self.switch_status = True
        print(f"{self.name} is now active with switch_status = {self.switch_status}.")

    def deactivate(self):
        self.device_status = "offline"
        self.actual_output = 0
        self.switch_status = False
        print(f"{self.name} is now inactive with switch_status = {self.switch_status}.")

    def increase_output(self, amount, is_percent=True):
        if self.device_status != "online":
            print(f"{self.name} is not active.")
            return 0, 0

        initial_output = self.actual_output
        if is_percent:
            increase_amount = initial_output * (amount / 100)
        else:
            increase_amount = amount

        new_output = min(initial_output + increase_amount, self.max_output)
        actual_increase = new_output - initial_output
        self.actual_output = new_output

        percent_increase = (
            (actual_increase / initial_output) * 100 if initial_output > 0 else 0
        )

        print(
            f"{self.name} output increased by {actual_increase:.2f} kW ({percent_increase:.2f}%) to {self.actual_output:.2f} kW"
        )
        return percent_increase, actual_increase

    def decrease_output(self, amount, is_percent=True):
        if self.device_status != "online":
            print(f"{self.name} is not active.")
            return 0, 0

        initial_output = self.actual_output
        if is_percent:
            decrease_amount = initial_output * (amount / 100)
        else:
            decrease_amount = amount

        new_output = max(initial_output - decrease_amount, self.min_output)
        actual_decrease = initial_output - new_output
        self.actual_output = new_output

        percent_decrease = (
            (actual_decrease / initial_output) * 100 if initial_output > 0 else 0
        )

        print(
            f"{self.name} output decreased by {actual_decrease:.2f} kW ({percent_decrease:.2f}%) to {self.actual_output:.2f} kW"
        )
        return percent_decrease, actual_decrease

    def set_output(self, amount):
        if self.device_status != "online":
            print(f"{self.name} is not active.")
            return

        if amount > self.max_output:
            print(f"{self.name} output set to its maximum: {self.max_output} kW")
            self.actual_output = self.max_output
        elif amount < self.min_output:
            print(f"{self.name} output set to its minimum: {self.min_output} kW")
            self.actual_output = self.min_output
        else:
            print(f"{self.name} output set to {amount} kW")
            self.actual_output = amount

    def increase_output_to_full_capacity(self):
        if self.device_status != "online":
            print(f"{self.name} is not active.")
            return 0

        increase_amount = self.max_output - self.actual_output
        self.actual_output = self.max_output
        print(f"{self.name} output increased to its maximum: {self.max_output} kW")
        return increase_amount

    def activate_and_set_to_full_capacity(self):
        if self.device_status == "offline":
            self.activate()

        if self.device_status == "online":
            return self.increase_output_to_full_capacity()
        else:
            print(f"Failed to activate {self.name}")
            return 0

    def try_activate(self, attempts=3, delay=5):
        initial_status = self.device_status
        for attempt in range(attempts):
            self.activate()
            time.sleep(delay)
            if self.device_status == "online" and self.device_status != initial_status:
                print(f"{self.name} activated successfully on attempt {attempt + 1}.")
                return True
            print(f"Attempt {attempt + 1} to activate {self.name} failed.")
        print(f"Failed to activate {self.name} after {attempts} attempts.")
        return False

    def try_deactivate(self, attempts=3, delay=5):
        initial_status = self.device_status
        for attempt in range(attempts):
            self.deactivate()
            time.sleep(delay)
            if self.device_status == "offline" and self.device_status != initial_status:
                print(f"{self.name} deactivated successfully on attempt {attempt + 1}.")
                return True
            print(f"Attempt {attempt + 1} to deactivate {self.name} failed.")
        print(f"Failed to deactivate {self.name} after {attempts} attempts.")
        return False

    def try_increase_output(self, amount, is_percent=True, attempts=3, delay=5):
        initial_output = self.actual_output
        for attempt in range(attempts):
            percent_increased, amount_increased = self.increase_output(
                amount, is_percent
            )
            time.sleep(delay)
            if self.actual_output > initial_output:
                print(
                    f"{self.name} output increased successfully on attempt {attempt + 1}."
                )
                return percent_increased, amount_increased
            print(f"Attempt {attempt + 1} to increase output of {self.name} failed.")
        print(f"Failed to increase output of {self.name} after {attempts} attempts.")
        return 0, 0

    def try_decrease_output(self, amount, is_percent=True, attempts=3, delay=5):
        initial_output = self.actual_output
        for attempt in range(attempts):
            percent_decreased, amount_decreased = self.decrease_output(
                amount, is_percent
            )
            time.sleep(delay)
            if self.actual_output < initial_output:
                print(
                    f"{self.name} output decreased successfully on attempt {attempt + 1}."
                )
                return percent_decreased, amount_decreased
            print(f"Attempt {attempt + 1} to decrease output of {self.name} failed.")
        print(f"Failed to decrease output of {self.name} after {attempts} attempts.")
        return 0, 0

    def update_state(self, data):
        """Update the state of the device with new data."""
        if self.validate_data(data):
            for key, value in data.items():
                setattr(self, key, value)
            print(f"{self.name} state updated successfully.")
            return True
        print(f"Failed to update {self.name} state due to invalid data.")
        return False

    def __str__(self):
        return f"{self.name} (ID: {self.id}): {self.actual_output}/{self.max_output} kW, Status: {self.device_status}"

    def __repr__(self):
        return (
            f"EnergySource(id={self.id}, name='{self.name}', priority={self.priority}, "
            f"max_output={self.max_output}, min_output={self.min_output}, "
            f"actual_output={self.actual_output}, switch_status={self.switch_status}, "
            f"device_status='{self.device_status}')"
        )
