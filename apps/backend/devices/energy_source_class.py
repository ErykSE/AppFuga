import time


class EnergySource:
    """
    Główna klasa dla urządzeń generujących moc. Dziedziczą z niej klasy: FuelCell, FuelTurbine, PV, WindTurbine.
    """

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
        is_adjustable=False,
    ):
        self.id = id
        self.name = name
        self.priority = priority
        self.max_output = max_output
        self.min_output = min_output if is_adjustable else 0
        self.actual_output = actual_output
        self.switch_status = switch_status
        self.device_status = device_status
        self.is_valid = False
        self.pending_action = None
        self.action_approved = None
        self.action_request_time = None
        self.is_adjustable = is_adjustable

    @staticmethod
    def validate_data(data):
        errors = []
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
                errors.append(f"Missing key: {key}")

        if not isinstance(data.get("id"), int) or data.get("id", 0) <= 0:
            errors.append(f"Invalid id: {data.get('id')}")
        if not isinstance(data.get("name"), str) or not data.get("name"):
            errors.append(f"Invalid name: {data.get('name')}")
        if not isinstance(data.get("priority"), int) or data.get("priority", 0) < 0:
            errors.append(f"Invalid priority: {data.get('priority')}")
        if (
            not isinstance(data.get("max_output"), (int, float))
            or data.get("max_output", 0) <= 0
        ):
            errors.append(f"Invalid max_output: {data.get('max_output')}")
        if (
            not isinstance(data.get("min_output"), (int, float))
            or data.get("min_output", 0) < 0
        ):
            errors.append(f"Invalid min_output: {data.get('min_output')}")
        if data.get("min_output", 0) > data.get("max_output", 0):
            errors.append(
                f"min_output ({data.get('min_output')}) is greater than max_output ({data.get('max_output')})"
            )
        if not isinstance(data.get("actual_output"), (int, float)):
            errors.append(f"Invalid actual_output: {data.get('actual_output')}")
        if not isinstance(data.get("switch_status"), bool):
            errors.append(f"Invalid switch_status: {data.get('switch_status')}")
        if data.get("device_status") not in ["online", "offline"]:
            errors.append(f"Invalid device_status: {data.get('device_status')}")

        # Jeśli urządzenie jest offline, pozwól na actual_output = 0
        if data.get("device_status") == "offline" and data.get("actual_output") != 0:
            errors.append(
                f"Offline device should have actual_output = 0, got: {data.get('actual_output')}"
            )

        return errors

    @classmethod
    def create_instance(cls, data):
        errors = cls.validate_data(data)
        if not errors:
            instance = cls(**data)
            instance.is_valid = True
            return instance
        else:
            return None

    def get_actual_output(self):
        return self.actual_output

    def get_max_output(self):
        return self.max_output

    def get_min_output(self):
        return self.min_output if self.is_adjustable else 0

    def get_status(self):
        return self.device_status

    def get_switch_status(self):
        return self.switch_status

    def get_name(self):
        return self.name

    def is_at_max_output(self):
        return self.actual_output >= self.max_output

    def activate(self):
        if self.device_status == "offline":
            self.device_status = "online"
            self.switch_status = True
            print(f"{self.name} is now active with output {self.actual_output} kW.")
            return True
        return False

    def deactivate(self):
        if self.device_status == "online":
            self.device_status = "offline"
            self.actual_output = 0
            self.switch_status = False
            print(f"{self.name} is now inactive.")
            return True
        return False

    def set_output(self, target_output):
        print(f"Attempting to set output for {self.name} to {target_output} kW")
        if self.device_status != "online":
            print(f"{self.name} is not active.")
            return False

        if not self.is_adjustable and target_output != self.max_output:
            print(f"{self.name} is not adjustable. Can only be set to maximum output.")
            return False

        if self.min_output <= target_output <= self.max_output:
            self.actual_output = target_output
            print(f"{self.name} output set to {target_output} kW")
            return True
        else:
            print(f"Target output {target_output} is out of range for {self.name}")
            return False

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

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "priority": self.priority,
            "max_output": self.max_output,
            "min_output": self.min_output,
            "actual_output": self.get_actual_output(),
            "switch_status": self.get_switch_status(),
            "device_status": "online" if self.get_switch_status() else "offline",
            "pending_action": self.pending_action,
            "action_approved": self.action_approved,
        }
