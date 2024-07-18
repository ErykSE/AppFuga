from apps.backend.managment.energy_surplus_manager_class import EnergySurplusManager
from apps.backend.managment.energy_deficit_manager_class import EnergyDeficitManager
import time
from threading import Thread


class EnergyManager:
    def __init__(self, microgrid, consumergrid, osd):
        self.microgrid = microgrid
        self.consumergrid = consumergrid
        self.osd = osd
        self.surplus_manager = EnergySurplusManager(microgrid, osd)
        self.deficit_manager = EnergyDeficitManager(microgrid, osd)
        self.running = False

    def start(self):
        self.running = True
        Thread(target=self.run_energy_management).start()

    def stop(self):
        self.running = False

    def run_energy_management(self):
        while self.running:
            self.check_energy_conditions()
            time.sleep(60)  # Sprawdzaj co minutę

    def check_energy_conditions(self):
        total_generated_power = self.microgrid.total_power_generated()
        total_demand_power = self.consumergrid.total_power_consumed()
        print(f"Total generated power: {total_generated_power} kW")
        print(f"Total demand power: {total_demand_power} kW")

        if total_generated_power >= total_demand_power:
            print(
                "Generated power meets or exceeds demand - power surplus algorithm starting"
            )
            power_surplus = total_generated_power - total_demand_power
            self.manage_surplus(power_surplus)
        else:
            print(
                "Generated power is less than demand - power deficit algorithm starting"
            )
            power_deficit = total_demand_power - total_generated_power
            self.manage_deficit(power_deficit)

    def manage_surplus(self, power_surplus):
        while power_surplus > 0:
            result = self.surplus_manager.manage_surplus_energy(power_surplus)
            power_surplus = result["remaining_surplus"]
            time.sleep(30)  # Sprawdzaj warunki co 30 sekund
            if power_surplus > 0:
                # Aktualizuj warunki energetyczne
                new_total_generated = self.microgrid.total_power_generated()
                new_total_demand = self.consumergrid.total_power_consumed()
                new_surplus = new_total_generated - new_total_demand
                if new_surplus <= 0:
                    print("Energy conditions changed, exiting surplus management")
                    break
                power_surplus = new_surplus

    def manage_deficit(self, power_deficit):
        # Podobna implementacja dla zarządzania deficytem
        pass
