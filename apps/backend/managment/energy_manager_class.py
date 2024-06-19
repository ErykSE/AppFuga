class EnergyManager:
    def __init__(self, microgrid, osd, contract, demand_power):
        self.microgrid = microgrid
        self.osd = osd
        self.contract = contract
        self.demand_power = demand_power

    def check_energy_conditions(self):
        total_generated_power = self.calculate_total_generated_power()
        print(f"Total generated power: {total_generated_power} kW")
        print(f"Demand power: {self.demand_power} kW")

        if total_generated_power >= self.demand_power:
            print("Generated power meets or exceeds demand.")
            power_surplus = total_generated_power - self.demand_power
            self.check_export_possibility(power_surplus)
        else:
            print("Generated power is less than demand.")

    def calculate_total_generated_power(self):
        total_power = (
            self.microgrid.pv_panels.total_power_generated()
            + self.microgrid.wind_turbines.total_power_generated()
            + self.microgrid.fuel_turbines.total_power_generated()
            + self.microgrid.fuel_cells.total_power_generated()
        )
        return total_power

    def check_export_possibility(self, power_surplus):
        if self.is_export_possible():
            print("Export is possible.")
            self.decide_to_sell_energy(power_surplus)
        else:
            print("Export is not possible. Limiting generated power.")
            self.limit_generated_power(power_surplus)

    def is_export_possible(self):
        return self.contract.get_is_export_possible()

    def decide_to_sell_energy(self, power_surplus):
        if self.should_sell_energy():
            if self.check_sale_limit(power_surplus):
                print("Deciding to sell energy based on current tariff rate.")
                self.sell_energy(power_surplus)
            else:
                print("Sale limit reached. Selling remaining allowable energy.")
                remaining_power = self.get_remaining_sale_power()
                self.sell_energy(remaining_power)
                self.handle_surplus_without_selling(power_surplus - remaining_power)
        else:
            print("Deciding not to sell energy.")
            self.handle_surplus_without_selling(power_surplus)

    def should_sell_energy(self):
        # current_tariff = self.osd.tariff  # Pobierz aktualną taryfę
        # logika do zaimplementowania
        pass

    def check_sale_limit(self, power_surplus):
        sale_limit = self.contract.get_sale_limit()
        if self.osd.get_sold_power() + power_surplus > sale_limit:
            print(f"Sale limit of {sale_limit} kW will be reached.")
            return False
        return True

    def get_remaining_sale_power(self):
        sale_limit = self.contract.get_sale_limit()
        remaining_power = sale_limit - self.osd.get_sold_power()
        return remaining_power

    def sell_energy(self, power_surplus):
        self.osd.update_sold_power(power_surplus)
        print(
            f"Selling {power_surplus} kW of surplus energy. Total energy sold: {self.osd.get_sold_power()} kW."
        )

    def handle_surplus_without_selling(self, power_surplus):
        if self.check_bess_availability():
            if self.check_bess_charge():
                print("BESS is charged. Handling surplus energy.")
                self.handle_charged_bess(power_surplus)
            else:
                print("BESS is not charged. Charging BESS.")
                self.charge_bess(power_surplus)
        else:
            print("No available BESS to use. Limiting generated power.")
            self.limit_generated_power(power_surplus)

    def check_bess_availability(self):
        for bess in self.microgrid.bess_units.devices:
            if bess.is_switch_closed():
                print("BESS is available and the switch is closed.")
                return True
        print("BESS is not available or the switch is open.")
        return False

    def check_bess_charge(self):
        for bess in self.microgrid.bess_units.devices:
            if bess.is_charged():
                return True
        return False

    def handle_charged_bess(self, power_surplus):
        self.check_export_possibility(power_surplus)  # Sprawdzic

    def charge_bess(self, power_surplus):
        for bess in self.microgrid.bess_units.devices:
            if not bess.is_charged():
                bess.charge()
                break  # Ładowanie tylko jednego BESS na raz
        print(f"Charging BESS with {power_surplus} kW surplus power.")
