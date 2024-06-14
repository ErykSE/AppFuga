class BESS(EnergySource):
    def __init__(self, power, capacity, charged):
        super().__init__(power)
        self.capacity = capacity  # Capacity of BESS in kWh
        self.charged = charged  # Whether the BESS is currently charged

    def get_current_power(self):
        return self.power

    def is_charged(self):
        return self.charged

    def charge(self):
        print("Charging BESS")
        self.charged = True

    def discharge(self):
        print("Discharging BESS")
        self.charged = False
