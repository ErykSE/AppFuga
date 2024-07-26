from apps.backend.devices.energy_point_class import EnergyPoint


class AdjustableDevice(EnergyPoint):
    """
    Klasa dla urządzeń/odbiorów, które można regulować w sposób zwiększania/zmniejszania zapotrzebowania. Będzie ona dziedziczyć z głównej klasy EnergyPoint.
    """

    def __init__(self, id, name, priority, power, switch_status, min_power, max_power):
        super().__init__(id, name, priority, power, switch_status)
        self.min_power = min_power
        self.max_power = max_power

    def increase_power(self, amount):
        new_power = self.power + amount
        if new_power > self.max_power:
            self.power = self.max_power
        else:
            self.power = new_power
        print(f"{self.name} power increased to {self.power} kW")

    def decrease_power(self, amount):
        new_power = self.power - amount
        if new_power < self.min_power:
            self.power = self.min_power
        else:
            self.power = new_power
        print(f"{self.name} power decreased to {self.power} kW")

    def to_dict(self):
        base_dict = super().to_dict()
        base_dict.update({"min_power": self.min_power, "max_power": self.max_power})
        return base_dict
