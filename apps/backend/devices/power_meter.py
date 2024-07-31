class PowerMeter:
    def __init__(self, id, name, status, measured_power, device_id):
        self.id = id
        self.name = name
        self.status = status
        self.measured_power = measured_power
        self.device_id = device_id

    @staticmethod
    def validate_data(data):
        errors = []
        if not isinstance(data.get("id"), int) or data.get("id", 0) <= 0:
            errors.append(f"Invalid id: {data.get('id')}")
        if not isinstance(data.get("name"), str) or not data.get("name"):
            errors.append(f"Invalid name: {data.get('name')}")
        if data.get("status") not in ["online", "offline"]:
            errors.append(f"Invalid status: {data.get('status')}")
        if (
            not isinstance(data.get("measured_power"), (int, float))
            or data.get("measured_power", 0) < 0
        ):
            errors.append(f"Invalid measured_power: {data.get('measured_power')}")
        if not isinstance(data.get("device_id"), int) or data.get("device_id", 0) <= 0:
            errors.append(f"Invalid device_id: {data.get('device_id')}")
        return errors

    @classmethod
    def create_instance(cls, data):
        errors = cls.validate_data(data)
        if not errors:
            return cls(**data)
        return None

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status,
            "measured_power": self.measured_power,
            "device_id": self.device_id,
        }
