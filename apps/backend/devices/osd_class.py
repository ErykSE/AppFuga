from apps.backend.devices.energy_class import EnergySource


class OSD(EnergySource):
    def __init__(self, power, tariff):
        super().__init__(power)
        self.tariff = tariff  # Tariff rate per kWh

    def get_current_power(self):
        return self.power
