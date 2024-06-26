class EnergyPoint:
    def __init__(self, id, name, priority, power, switch_status):
        self.id = id
        self.name = name
        self.priority = priority
        self.power = power
        self.switch_status = switch_status
        self.is_valid = False

    def get_current_power(self):
        return self.power

    def get_switch_status(self):
        return self.switch_status

    def activate(self):
        self.switch_status = True
        print(f"{self.name} is now active with switch_status = {self.switch_status}.")

    def deactivate(self):
        self.switch_status = False
        print(f"{self.name} is now inactive with switch_status = {self.switch_status}.")

    @staticmethod
    def validate_data(data, required_keys):
        for key in required_keys:
            if key not in data:
                print(f"Missing key: {key} in data: {data}")
                return False
        return True

    @classmethod
    def create_instance(cls, data):
        required_keys = [
            "id",
            "name",
            "priority",
            "power",
            "switch_status",
            "device_type",
        ]
        if cls.validate_data(data, required_keys):
            instance = cls(**data)
            instance.is_valid = True
            return instance
        return None
