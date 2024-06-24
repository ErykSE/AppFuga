from apps.backend.managment.energy_surplus_manager_class import EnergySurplusManager
from apps.backend.managment.energy_deficit_manager_class import EnergyDeficitManager


class EnergyManager:
    def __init__(self, microgrid, osd, contract, demand_power):
        self.microgrid = microgrid
        self.osd = osd
        self.contract = contract
        self.demand_power = demand_power
        self.surplus_manager = EnergySurplusManager(microgrid, osd, contract)
        self.deficit_manager = EnergyDeficitManager(microgrid, osd, contract)

    def check_energy_conditions(self):
        total_generated_power = self.calculate_total_generated_power()
        print(f"Total generated power: {total_generated_power} kW")
        print(f"Demand power: {self.demand_power} kW")

        if total_generated_power >= self.demand_power:
            print("Generated power meets or exceeds demand.")
            power_surplus = total_generated_power - self.demand_power
            self.surplus_manager.handle_surplus(power_surplus)
        else:
            print("Generated power is less than demand.")
            power_deficit = self.demand_power - total_generated_power
            self.deficit_manager.handle_deficit(power_deficit)

    def calculate_total_generated_power(self):
        total_power = (
            self.microgrid.pv_panels.total_power_generated()
            + self.microgrid.wind_turbines.total_power_generated()
            + self.microgrid.fuel_turbines.total_power_generated()
            + self.microgrid.fuel_cells.total_power_generated()
        )
        return total_power
