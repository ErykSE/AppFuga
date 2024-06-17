from apps.backend.devices.energy_class import EnergySource


class BESS(EnergySource):
    def __init__(self, power, capacity, is_switch_closed):
        super().__init__(power)
        self.capacity = capacity  # Capacity of BESS in kWh
        self.is_switch_closed = is_switch_closed

    def get_current_power(self):
        return self.power

    def is_switch_closed(self):
        return self.is_switch_closed

    def charge(self):
        print("Charging BESS")
        self.charged = True

    def discharge(self):
        print("Discharging BESS")
        self.charged = False
