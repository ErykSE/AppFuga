from apps.backend.devices.energy_class import EnergySource


class FuelCell(EnergySource):
    def __init__(self, power):
        super().__init__(power)

    def get_current_power(self):
        return self.power
