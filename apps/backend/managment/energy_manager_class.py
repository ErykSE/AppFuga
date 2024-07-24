import logging
from apps.backend.managment.energy_surplus_manager_class import EnergySurplusManager
from apps.backend.managment.energy_deficit_manager_class import EnergyDeficitManager


from threading import Thread, Event


class EnergyManager:
    """
    Główna klasa zarządzająca energią. Sprawdzana jest tutaj aktualna sytuacja i na tej podstawie załączane sa odpowiednie klasy
    odpowiednio do zarządzania nadwyżką lub deficytem.
    """

    def __init__(
        self, microgrid, consumergrid, osd, info_logger, error_logger, check_interval=60
    ):
        self.microgrid = microgrid
        self.consumergrid = consumergrid
        self.osd = osd
        self.info_logger = info_logger
        self.error_logger = error_logger
        self.surplus_manager = EnergySurplusManager(
            microgrid, osd, info_logger, error_logger
        )
        self.deficit_manager = EnergyDeficitManager(
            microgrid, osd, info_logger, error_logger
        )
        self.check_interval = check_interval
        self.running = False
        self.stop_event = Event()

    def start(self):
        self.running = True
        self.stop_event.clear()
        Thread(target=self.run_energy_management).start()
        self.info_logger.info("Energy management started")

    def stop(self):
        self.running = False
        self.stop_event.set()
        self.info_logger.info("Energy management stopping")

    def run_energy_management(self):
        while self.running and not self.stop_event.is_set():
            try:
                self.info_logger.info(
                    "Starting a new iteration of the energy management algorithm"
                )
                self.check_energy_conditions()
                self.stop_event.wait(self.check_interval)
            except Exception as e:
                self.error_logger.error(f"Error in energy management: {str(e)}")

    def check_energy_conditions(self):
        try:
            self.log_system_summary()
            total_generated_power = self.microgrid.total_power_generated()
            total_demand_power = self.consumergrid.total_power_consumed()

            if total_generated_power > total_demand_power:
                self.info_logger.info(
                    "##### Power surplus detected - starting surplus management #####"
                )
                power_surplus = total_generated_power - total_demand_power
                self.manage_surplus(power_surplus)
            elif total_generated_power < total_demand_power:
                self.info_logger.info(
                    "##### Power deficit detected - starting deficit management #####"
                )
                power_deficit = total_demand_power - total_generated_power
                self.manage_deficit(power_deficit)
            else:
                self.info_logger.info(
                    "##### Power generation matches demand - no action needed #####"
                )
        except Exception as e:
            self.error_logger.error(f"Error checking energy conditions: {str(e)}")

    def manage_surplus(self, power_surplus):
        while power_surplus > 0 and not self.stop_event.is_set():
            try:
                result = self.surplus_manager.manage_surplus_energy(power_surplus)
                power_surplus = result["remaining_surplus"]
                if self.stop_event.wait(30):  # Sprawdzaj warunki co 30 sekund
                    break
                if power_surplus > 0:
                    new_total_generated = self.microgrid.total_power_generated()
                    new_total_demand = self.consumergrid.total_power_consumed()
                    new_surplus = new_total_generated - new_total_demand
                    if new_surplus <= 0:
                        self.info_logger.info(
                            "Energy conditions changed, exiting surplus management"
                        )
                        break
                    power_surplus = new_surplus

            except Exception as e:
                self.error_logger.error(f"Error in surplus management: {str(e)}")
                break

    def manage_deficit(self, power_deficit):
        initial_deficit = power_deficit
        self.info_logger.info(f"Rozpoczęcie zarządzania deficytem: {power_deficit} kW")

        max_iterations = 5  # Dodajemy maksymalną liczbę iteracji
        iteration = 0

        while (
            power_deficit > 0
            and not self.stop_event.is_set()
            and iteration < max_iterations
        ):
            try:
                iteration += 1
                self.info_logger.info(f"Iteracja {iteration} zarządzania deficytem")

                result = self.deficit_manager.handle_deficit(power_deficit)
                managed_amount = result["amount_managed"]
                power_deficit = result["remaining_deficit"]

                self.info_logger.info(
                    f"Zarządzono {managed_amount} kW deficytu. Pozostało: {power_deficit} kW"
                )

                if managed_amount == 0:
                    self.info_logger.warning(
                        "Nie udało się zarządzić żadną częścią deficytu w tej iteracji."
                    )
                    if iteration == max_iterations:
                        self.info_logger.warning(
                            "Osiągnięto maksymalną liczbę iteracji bez pełnego rozwiązania deficytu."
                        )
                        break

                if self.stop_event.wait(
                    10
                ):  # Zmniejszamy czas oczekiwania do 10 sekund
                    break

                # Aktualizacja warunków
                new_total_generated = self.microgrid.total_power_generated()
                new_total_demand = self.consumergrid.total_power_consumed()
                new_deficit = new_total_demand - new_total_generated

                self.info_logger.info(
                    f"Aktualna generacja: {new_total_generated} kW, Aktualne zapotrzebowanie: {new_total_demand} kW"
                )

                if new_deficit <= 0:
                    self.info_logger.info(
                        "Warunki energetyczne zmieniły się, deficyt został rozwiązany"
                    )
                    break

                power_deficit = new_deficit
                self.info_logger.info(f"Zaktualizowany deficyt: {power_deficit} kW")

            except Exception as e:
                self.error_logger.error(f"Błąd w zarządzaniu deficytem: {str(e)}")
                break

        if power_deficit > 0:
            self.info_logger.warning(
                f"Zakończono zarządzanie deficytem. Pozostały nierozwiązany deficyt: {power_deficit} kW"
            )
        else:
            self.info_logger.info(
                "Zakończono zarządzanie deficytem. Cały deficyt został rozwiązany."
            )

    def log_system_summary(self):
        total_generated_power = self.microgrid.total_power_generated()
        total_demand_power = self.consumergrid.total_power_consumed()
        active_devices = self.microgrid.get_active_devices()
        inactive_devices = self.microgrid.get_inactive_devices()

        summary = [
            "Summary of system status:",
            f"Total generated power: {total_generated_power} kW",
            f"Total demand: {total_demand_power} kW",
            f"Number of active devices: {len(active_devices)}",
            f"Number of inactive devices: {len(inactive_devices)}",
            "Active devices:",
        ]

        for device in active_devices:
            summary.append(
                f"  - {device.name}, latest power: {device.get_actual_output()} kW, max power: {device.get_max_output()} kW"
            )

        summary.append("Inactive devices:")
        for device in inactive_devices:
            summary.append(
                f"  - {device.name} , max power: {device.get_max_output()} kW"
            )

        if self.microgrid.bess:
            bess = self.microgrid.bess
            summary.append(
                f"BESS, charge level: {bess.get_charge_level()} kWh, available capacity: {bess.get_capacity() - bess.get_charge_level()} kWh"
            )

        summary.extend(
            [
                f"Possibility to purchase energy: {'Yes' if self.osd.can_buy_energy() else 'No'}",
                f"Energy purchase limit: {self.osd.get_purchase_limit()} kWh",
                f"Current amount of energy purchased: {self.osd.get_bought_power()} kWh",
                f"Possibility to sell energy: {'Yes' if self.osd.can_sell_energy() else 'No'}",
                f"Energy sell limit: {self.osd.get_sale_limit()} kWh",
                f"Current amount of energy sold: {self.osd.get_sold_power()} kWh",
            ]
        )

        for line in summary:
            self.info_logger.info(line)
