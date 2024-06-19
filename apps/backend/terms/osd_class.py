class OSD:
    def __init__(self, tariff, sold_power):
        self.tariff = tariff  # Tariff rate per kWh
        self.sold_power = sold_power

    def get_sold_power(self):
        return self.sold_power

    def get_current_tarrif(self):
        return self.tariff

    def update_sold_power(self, new_power):
        self.sold_power += new_power
