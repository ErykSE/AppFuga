class OSD:
    def __init__(self, tariff, sold_power, power):
        self.tariff = tariff  # Tariff rate per kWh
        self.sold_power = sold_power
        self.power = power

    def get_sold_power(self):
        return self.sold_power

    def get_current_tarrif(self):
        return self.tariff

    def get_current_power(self):
        return self.power
