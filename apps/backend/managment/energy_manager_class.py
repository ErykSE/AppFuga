import json
import logging
import time
from apps.backend.managment.energy_surplus_manager_class import EnergySurplusManager
from apps.backend.managment.energy_deficit_manager_class import EnergyDeficitManager
from apps.backend.others.data_validator import DataValidator

from threading import Thread, Event


class EnergyManager:
    """
    Główna klasa zarządzająca energią w systemie mikrosieciowym.

    Klasa ta odpowiada za monitorowanie i zarządzanie bilansem energetycznym,
    obsługując zarówno nadwyżki, jak i deficyty energii. Wykorzystuje ona
    osobne menedżery do obsługi nadwyżek (EnergySurplusManager) i deficytów
    (EnergyDeficitManager).

    Attributes:
        microgrid (object): Obiekt reprezentujący mikrosieć.
        consumergrid (object): Obiekt reprezentujący sieć konsumentów.
        osd (object): Obiekt reprezentujący operatora systemu dystrybucyjnego.
        info_logger (logging.Logger): Logger do zapisywania informacji.
        error_logger (logging.Logger): Logger do zapisywania błędów.
        surplus_manager (EnergySurplusManager): Menedżer do obsługi nadwyżek energii.
        deficit_manager (EnergyDeficitManager): Menedżer do obsługi deficytów energii.
        check_interval (int): Interwał czasowy między kolejnymi sprawdzeniami (w sekundach).
        running (bool): Flaga wskazująca, czy menedżer jest aktualnie uruchomiony.
        stop_event (threading.Event): Wydarzenie do sygnalizacji zatrzymania.
        restart_delay (int): Opóźnienie przed ponownym uruchomieniem (w sekundach).
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
            microgrid, consumergrid, osd, info_logger, error_logger
        )
        self.check_interval = check_interval
        self.running = False
        self.stop_event = Event()
        self.restart_delay = 30  # czas oczekiwania przed ponownym startem (w sekundach)

    def start(self):
        """
        Uruchamia proces zarządzania energią w osobnym wątku.
        """
        self.running = True
        self.stop_event.clear()
        Thread(target=self.run_energy_management).start()
        self.info_logger.info("Energy management started")

    def stop(self):
        """
        Zatrzymuje proces zarządzania energią.
        """
        self.running = False
        self.stop_event.set()
        self.info_logger.info("Energy management stopping")

    def run_energy_management(self):
        """
        Główna pętla zarządzania energią. Wykonuje cykliczne sprawdzenia
        i zarządzanie bilansem energetycznym.
        """
        while self.running and not self.stop_event.is_set():
            try:
                self.run_single_iteration()

                # Zapisz aktualny stan do pliku JSON
                self.save_live_data()

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
        """
        Wykonuje pojedynczą iterację algorytmu zarządzania energią.
        Obejmuje wczytywanie danych, walidację, logowanie stanu systemu
        i sprawdzenie warunków energetycznych.
        """
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
        """
        Przygotowuje dane mikrosieci do walidacji.

        Returns:
            dict: Słownik zawierający dane wszystkich urządzeń w mikrosieci.
        """
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
        """
        Pomocnicza metoda do uzyskania listy urządzeń.

        Args:
            devices (object or list): Pojedyncze urządzenie lub lista urządzeń.

        Returns:
            list: Lista urządzeń.
        """
        if isinstance(devices, list):
            return devices
        elif devices:
            return [devices]
        else:
            return []

    def handle_validation_errors(self, microgrid_errors, osd_errors):
        """
        Obsługuje błędy walidacji danych mikrosieci i OSD.

        Args:
            microgrid_errors (list): Lista błędów walidacji danych mikrosieci.
            osd_errors (list): Lista błędów walidacji danych OSD.
        """
        self.info_logger.error("Validation errors detected. Stopping the algorithm.")
        for error in microgrid_errors:
            self.error_logger.error(f"Microgrid validation error: {error}")
        for error in osd_errors:
            self.error_logger.error(f"OSD validation error: {error}")
        self.stop()

    def handle_runtime_error(self, e):
        """
        Obsługuje błędy wykonania występujące podczas zarządzania energią.

        Args:
            e (Exception): Wyjątek, który wystąpił.
        """
        self.error_logger.error(f"Error in energy management: {str(e)}")
        self.error_logger.exception("Full traceback:")
        self.info_logger.error("An error occurred. Stopping the algorithm.")
        self.stop()

    def check_energy_conditions(self):
        """
        Sprawdza warunki energetyczne i inicjuje odpowiednie działania
        w przypadku nadwyżki lub deficytu energii.
        """
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
        """
        Zarządza nadwyżką energii.

        Args:
            power_surplus (float): Wartość nadwyżki energii w kW.
        """
        result = self.surplus_manager.manage_surplus_energy(power_surplus)
        managed_amount = result["amount_managed"]
        remaining_surplus = result["remaining_surplus"]

        self.info_logger.info(
            f"Managed {managed_amount} kW of surplus. Remaining: {remaining_surplus} kW"
        )

        if remaining_surplus > 0:
            self.info_logger.warning(
                f"Surplus management completed. Remaining unresolved surplus: {remaining_surplus} kW"
            )
        else:
            self.info_logger.info(
                "Surplus management completed. The entire surplus has been dissolved."
            )

    def manage_deficit(self, power_deficit):
        """
        Zarządza deficytem energii.

        Args:
            power_deficit (float): Wartość deficytu energii w kW.
        """
        result = self.deficit_manager.handle_deficit(power_deficit)
        managed_amount = result["amount_managed"]
        remaining_deficit = result["remaining_deficit"]

        self.info_logger.info(
            f"Managed {managed_amount} kW of deficit. Remaining: {remaining_deficit} kW"
        )

        if remaining_deficit > 0:
            self.info_logger.warning(
                f"Deficit management has been completed. Remaining unresolved deficit: {remaining_deficit} kW"
            )
        else:
            self.info_logger.info(
                "Deficit management has been completed. The entire deficit has been resolved."
            )

    def log_system_summary(self):
        """
        Loguje podsumowanie stanu systemu, w tym informacje o generacji,
        zapotrzebowaniu, aktywnych i nieaktywnych urządzeniach oraz BESS.
        """
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

    def save_live_data(self):
        """
        Generuje i zapisuje aktualny stan wszystkich urządzeń do pliku JSON.
        """
        live_data = {
            "pv_panels": [panel.to_dict() for panel in self.microgrid.pv_panels],
            "wind_turbines": [
                turbine.to_dict() for turbine in self.microgrid.wind_turbines
            ],
            "fuel_turbines": [
                turbine.to_dict() for turbine in self.microgrid.fuel_turbines
            ],
            "fuel_cells": [cell.to_dict() for cell in self.microgrid.fuel_cells],
            "bess": [self.microgrid.bess.to_dict()] if self.microgrid.bess else [],
            "non_adjustable_devices": [
                device.to_dict() for device in self.consumergrid.non_adjustable_devices
            ],
            "adjustable_devices": [
                device.to_dict() for device in self.consumergrid.adjustable_devices
            ],
        }

        with open("C:/eryk/AppFuga/apps/backend/live_data.json", "w") as f:
            json.dump(live_data, f, indent=4)

        self.info_logger.info("Live data saved to live_data.json")
