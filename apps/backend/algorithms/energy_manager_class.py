class EnergyManager:
    def __init__(self, microgrid, osd, contract, demand_power):
        self.microgrid = microgrid
        self.osd = osd
        self.contract = contract
        self.demand_power = demand_power
        self.total_energy_sold = 0

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

    def decide_to_sell_energy(self):
        # Placeholder for decision logic to sell energy
        # Here we can consider tariff rates and other factors
        current_tarrif = self.osd.tariff
        return current_tarrif > 0.1

    ##### to implement #########

    def limit_generated_power(self, power_surplus):
        contracted_power = self.contract.get_contracted_power()
        margin = self.contract.get_margin()
        excess_power = power_surplus - (
            contracted_power * (1 + margin) - self.demand_power
        )

        if excess_power > 0:
            for pv in self.microgrid.pv_panels.devices:
                pv.adjust_regulator(
                    pv.get_current_power()
                    - excess_power / len(self.microgrid.pv_panels.devices)
                )
        print(
            f"Reduced power generation. Current PV power: {self.microgrid.pv_panels.total_power_generated()} kW"
        )


####### to implement #########


##########
"""
    def manage_export(self):
        if self.contract.get_is_export_possible():
            if not self.bess.is_charged():
                self.bess.charge()
            else:
                if self.contract.get_is_sale_possible():
                    if self.total_energy_sold < self.contract.get_sale_limit():
                        self.export_energy()
                    else:
                        print("Sale limit reached. Cannot export more energy.")
                else:
                    print("Export is possible but sale is not allowed.")
        else:
            self.reduce_generation()

    def manage_import(self):
        if not self.bess.is_charged():
            self.bess.charge()
        else:
            self.bess.discharge()

        if self.osd.get_current_power() > self.pv.get_current_power():
            self.activate_loads()

    def is_export_possible(self):
        return self.contract.get_is_export_possible()

    def export_energy(self):
        if self.contract.get_is_sale_possible():
            sale_limit = self.contract.get_sale_limit()
            energy_to_sell = min(
                sale_limit - self.total_energy_sold, self.pv.get_current_power()
            )
            self.total_energy_sold += energy_to_sell
            print(
                f"Exporting {energy_to_sell} kWh to OSD, total energy sold: {self.total_energy_sold} kWh (limit: {sale_limit} kWh)"
            )
        else:
            print("Exporting energy to OSD")

    def reduce_generation(self):
        CONTRACTED_POWER = self.contract.get_contracted_power()
        MARGIN = self.contract.get_margin()
        moc_generowana = self.pv.get_current_power()
        moc_przekroczenia = moc_generowana - (CONTRACTED_POWER * (1 + MARGIN))

        if moc_przekroczenia > 0:
            self.pv.adjust_regulator(moc_generowana - moc_przekroczenia)
        else:
            self.pv.adjust_regulator(moc_generowana)

        print(
            f"Reducing power generation, current PV power: {self.pv.get_current_power()} kW"
        )

    def activate_loads(self):
        print("Activating additional loads")
"""
