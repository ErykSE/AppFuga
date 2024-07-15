from apps.backend.managment.energy_surplus_manager_class import EnergySurplusManager
from apps.backend.managment.energy_deficit_manager_class import EnergyDeficitManager


class EnergyManager:
    def __init__(self, microgrid, consumergrid, osd):
        self.microgrid = microgrid
        self.consumergrid = consumergrid
        self.osd = osd
        self.surplus_manager = EnergySurplusManager(microgrid, osd)
        self.deficit_manager = EnergyDeficitManager(microgrid, osd)

    def check_energy_conditions(self):
        total_generated_power = self.microgrid.total_power_generated()
        total_demand_power = self.consumergrid.total_power_consumed()
        print(f"Total generated power: {total_generated_power} kW")
        print(f"Total demand power: {total_demand_power} kW")

        if total_generated_power >= total_demand_power:
            print(
                "Generated power meets or exceeds demand - power surplus algorithm starting"
            )

            # power_surplus = total_generated_power - total_demand_power
            # self.surplus_manager.manage_surplus_energy(power_surplus)
        else:
            print(
                "Generated power is less than demand - power deficit algorithm starting"
            )
            # power_deficit = total_demand_power - total_generated_power
            # self.deficit_manager.handle_deficit(power_deficit)
