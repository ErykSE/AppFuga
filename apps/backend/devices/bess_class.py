import time


class BESS:
    """
    Klasa dla urządzenia magazynującego energię.
    """

    def __init__(
        self,
        id,
        name,
        capacity,
        min_charge_level,
        charge_level=0,
        switch_status=False,
        device_status="offline",
    ):
        self.id = id
        self.name = name
        self.capacity = capacity
        self.min_charge_level = min_charge_level
        self.charge_level = charge_level
        self.switch_status = switch_status
        self.device_status = device_status
        self.is_valid = False

    @staticmethod
    def validate_data(data):
        errors = []
        required_keys = [
            "id",
            "name",
            "capacity",
            "min_charge_level",
            "charge_level",
            "switch_status",
            "device_status",
        ]
        for key in required_keys:
            if key not in data:
                errors.append(f"Missing key: {key}")
        if not isinstance(data["id"], int) or data["id"] <= 0:
            errors.append(f"Invalid id: {data['id']}")
        if not isinstance(data["name"], str) or not data["name"]:
            errors.append(f"Invalid name: {data['name']}")
        if not isinstance(data["capacity"], (int, float)) or data["capacity"] < 0:
            errors.append(f"Invalid capacity: {data['capacity']}")
        if (
            not isinstance(data["charge_level"], (int, float))
            or data["charge_level"] < 0
        ):
            errors.append(f"Invalid charge_level: {data['charge_level']}")
        if not isinstance(data["switch_status"], bool):
            errors.append(f"Invalid switch_status: {data['switch_status']}")
        if data["device_status"] not in ["online", "offline"]:
            errors.append(f"Invalid device_status: {data['device_status']}")

        # Sprawdzamy warunki dla urządzenia online i włączonego
        # if data["device_status"] == "online" and data["switch_status"]:
        #     if data["capacity"] == 0:
        #         errors.append(
        #             "Capacity must be greater than 0 when BESS is online and switched on"
        #         )

        # Sprawdzamy warunki dla urządzenia offline lub wyłączonego
        # if data["device_status"] == "offline" or not data["switch_status"]:
        #     if data["charge_level"] > 0:
        #         errors.append(
        #             "Charge level must be 0 when BESS is offline or switched off"
        #         )
        if data["min_charge_level"] < 0 or data["min_charge_level"] > data["capacity"]:
            errors.append(f"Invalid min_charge_level: {data['min_charge_level']}")
        if data["charge_level"] < data["min_charge_level"]:
            errors.append(f"Charge level cannot be lower than min_charge_level")

        return errors

    @classmethod
    def create_instance(cls, data):
        errors = cls.validate_data(data)
        if not errors:
            instance = cls(**data)
            instance.is_valid = True
            print(f"Successfully created BESS instance: {instance.name}")
            return instance
        else:
            print(f"Failed to create BESS instance. Errors: {errors}")
            return None

    def activate(self):
        if self.charge_level > self.min_charge_level:
            self.device_status = "online"
            self.switch_status = True
            return True
        return False

    def deactivate(self):
        self.device_status = "offline"
        self.switch_status = False
        return True

    def charge(self, amount):
        new_charge_level = min(self.charge_level + amount, self.capacity)
        charged_amount = new_charge_level - self.charge_level
        self.charge_level = new_charge_level
        charged_percent = (charged_amount / self.capacity) * 100
        print(f"BESS charged: -> {new_charge_level} kWh ({charged_percent:.2f}%)")
        return charged_amount, charged_percent

    def discharge(self, amount):
        available_energy = self.charge_level - self.min_charge_level
        discharge_amount = min(amount, available_energy)
        self.charge_level -= discharge_amount
        discharged_percent = (discharge_amount / self.capacity) * 100
        print(
            f"BESS discharged: -> {self.charge_level} kWh ({discharged_percent:.2f}%)"
        )
        return discharge_amount, discharged_percent

    def get_charge_level(self):
        return self.charge_level

    def get_capacity(self):
        return self.capacity

    def get_status(self):
        return self.device_status

    def get_switch_status(self):
        return self.switch_status

    def get_available_energy(self):
        return self.charge_level - self.min_charge_level

    def is_uncharged(self):
        return self.charge_level < self.capacity

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "capacity": self.capacity,
            "min_charge_level": self.min_charge_level,
            "charge_level": self.charge_level,
            "switch_status": self.get_switch_status(),
            "device_status": self.get_status(),
        }
