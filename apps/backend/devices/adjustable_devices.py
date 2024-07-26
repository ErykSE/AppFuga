from apps.backend.devices.energy_point_class import EnergyPoint


class AdjustableDevice(EnergyPoint):
    """
    Klasa dla urządzeń/odbiorów, które można regulować w sposób zwiększania/zmniejszania zapotrzebowania. Będzie ona dziedziczyć z głównej klasy EnergyPoint.
    """

    def __init__(self, id, name, priority, power, switch_status, min_power, max_power):
        super().__init__(id, name, priority, power, switch_status)
        self.min_power = min_power
        self.max_power = max_power

    @staticmethod
    def validate_data(data):
        if not EnergyPoint.validate_data(data):
            return False
        if "min_power" not in data or "max_power" not in data:
            print(f"Missing min_power or max_power in data: {data}")
            return False
        if not isinstance(data["min_power"], (int, float)) or data["min_power"] < 0:
            print(f"Invalid min_power: {data['min_power']}")
            return False
        if (
            not isinstance(data["max_power"], (int, float))
            or data["max_power"] <= data["min_power"]
        ):
            print(f"Invalid max_power: {data['max_power']}")
            return False
        if data["power"] < data["min_power"] or data["power"] > data["max_power"]:
            print(
                f"Power {data['power']} is outside of allowed range [{data['min_power']}, {data['max_power']}]"
            )
            return False
        return True

    def set_power(self, new_power):
        if self.switch_status:
            if new_power < self.min_power:
                self.power = self.min_power
            elif new_power > self.max_power:
                self.power = self.max_power
            else:
                self.power = new_power
        else:
            self.power = 0
        print(f"{self.name} power set to {self.power} kW")

    def increase_power(self, amount):
        new_power = min(self.power + amount, self.max_power)
        self.set_power(new_power)
        return new_power - self.power  # zwraca faktycznie zwiększoną moc

    def decrease_power(self, amount):
        old_power = self.power
        new_power = max(self.power - amount, self.min_power)
        self.power = new_power
        actual_reduction = old_power - new_power
        print(f"{self.name} power decreased from {old_power} kW to {self.power} kW")
        return actual_reduction

    def activate(self):
        super().activate()
        self.power = self.min_power
        print(f"{self.name} activated with minimum power {self.min_power} kW")

    def get_reducible_power(self):
        return max(0, self.power - self.min_power)

    def to_dict(self):
        base_dict = super().to_dict()
        base_dict.update({"min_power": self.min_power, "max_power": self.max_power})
        return base_dict
