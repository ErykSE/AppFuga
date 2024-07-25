import logging
import time
from apps.backend.managment.energy_surplus_manager_class import EnergySurplusManager
from apps.backend.managment.energy_deficit_manager_class import EnergyDeficitManager
from apps.backend.others.data_validator import DataValidator

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
        self.restart_delay = 30  # czas oczekiwania przed ponownym startem (w sekundach)

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
                self.run_single_iteration()

                # Czekamy określony czas przed następną iteracją
                self.info_logger.info(
                    f"Oczekiwanie {self.restart_delay} sekund przed następną iteracją..."
                )
                if self.stop_event.wait(self.restart_delay):
                    break
            except Exception as e:
                self.handle_runtime_error(e)
                break

        self.info_logger.info("Energy management stopped")

    def run_single_iteration(self):
        self.info_logger.info(
            "Starting a new iteration of the energy management algorithm"
        )

        # Wczytywanie i walidacja danych
        microgrid_data = self.prepare_microgrid_data()
        microgrid_errors = DataValidator.validate_microgrid_data(microgrid_data)
        osd_errors = DataValidator.validate_contract_data(self.osd.__dict__)

        if microgrid_errors or osd_errors:
            self.handle_validation_errors(microgrid_errors, osd_errors)
            return

        # Logowanie stanu systemu
        self.log_system_summary()

        # Sprawdzenie warunków energetycznych
        self.check_energy_conditions()

    def prepare_microgrid_data(self):
        return {
            "pv_panels": self.get_device_list(self.microgrid.pv_panels),
            "wind_turbines": self.get_device_list(self.microgrid.wind_turbines),
            "fuel_turbines": self.get_device_list(self.microgrid.fuel_turbines),
            "fuel_cells": self.get_device_list(self.microgrid.fuel_cells),
            "bess": [self.microgrid.bess] if self.microgrid.bess else [],
            "non_adjustable_devices": self.get_device_list(
                self.consumergrid.non_adjustable_devices
            ),
            "adjustable_devices": self.get_device_list(
                self.consumergrid.adjustable_devices
            ),
        }

    def get_device_list(self, devices):
        if isinstance(devices, list):
            return devices
        elif devices:
            return [devices]
        else:
            return []

    def handle_validation_errors(self, microgrid_errors, osd_errors):
        self.info_logger.error("Validation errors detected. Stopping the algorithm.")
        for error in microgrid_errors:
            self.error_logger.error(f"Microgrid validation error: {error}")
        for error in osd_errors:
            self.error_logger.error(f"OSD validation error: {error}")
        self.stop()

    def handle_runtime_error(self, e):
        self.error_logger.error(f"Error in energy management: {str(e)}")
        self.error_logger.exception("Full traceback:")
        self.info_logger.error("An error occurred. Stopping the algorithm.")
        self.stop()

    def check_energy_conditions(self):
        try:
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
        result = self.surplus_manager.manage_surplus_energy(power_surplus)
        managed_amount = result["amount_managed"]
        remaining_surplus = result["remaining_surplus"]

        self.info_logger.info(
            f"Zarządzono {managed_amount} kW nadwyżki. Pozostało: {remaining_surplus} kW"
        )

        if remaining_surplus > 0:
            self.info_logger.warning(
                f"Zakończono zarządzanie nadwyżką. Pozostała nierozwiązana nadwyżka: {remaining_surplus} kW"
            )
        else:
            self.info_logger.info(
                "Zakończono zarządzanie nadwyżką. Cała nadwyżka została rozwiązana."
            )

    def manage_deficit(self, power_deficit):
        result = self.deficit_manager.handle_deficit(power_deficit)
        managed_amount = result["amount_managed"]
        remaining_deficit = result["remaining_deficit"]

        self.info_logger.info(
            f"Zarządzono {managed_amount} kW deficytu. Pozostało: {remaining_deficit} kW"
        )

        if remaining_deficit > 0:
            self.info_logger.warning(
                f"Zakończono zarządzanie deficytem. Pozostały nierozwiązany deficyt: {remaining_deficit} kW"
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
