class EnergyPoint:
    """
    Główna klasa dla urządzeń/odbiorów, które zużywają moc. Dziedziczyć z niej będą klasy: AdjustableDevice oraz NonAdjustableDevice.
    """

    def __init__(self, id, name, priority, power, switch_status):
        self.id = id
        self.name = name
        self.priority = priority
        self.power = power
        self.switch_status = switch_status
        self.is_valid = False

    @staticmethod
    def validate_data(data):
        required_keys = [
            "id",
            "name",
            "priority",
            "power",
            "switch_status",
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
        if not isinstance(data["power"], (int, float)) or data["power"] < 0:
            print(f"Invalid actual_output: {data['actual_output']}")
            return False
        if not isinstance(data["switch_status"], bool):
            print(f"Invalid switch_status: {data['switch_status']}")
            return False
        return True

    @classmethod
    def create_instance(cls, data):
        if cls.validate_data(data):
            instance = cls(**data)
            instance.is_valid = True
            return instance
        return None

    def get_current_power(self):
        return self.power

    def get_switch_status(self):
        return self.switch_status

    def activate(self):
        self.switch_status = True
        print(f"{self.name} activated")

    def deactivate(self):
        if self.switch_status:
            self.switch_status = False
            self.power = 0
            print(f"{self.name} deactivated")
            return True
        else:
            print(f"{self.name} is already deactivated")
            return False

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "priority": self.priority,
            "power": self.power,
            "switch_status": self.get_switch_status(),
        }

    def get_actual_output(self):
        return self.power if self.switch_status else 0
