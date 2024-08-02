from datetime import datetime
import json
from threading import Thread, Event
from apps.backend.managment.energy_surplus_manager_class import EnergySurplusManager
from apps.backend.managment.energy_deficit_manager_class import EnergyDeficitManager
from apps.backend.others.osd_class import OSD
from apps.backend.others.data_validator import DataValidator
from apps.backend.managment.power_profile_manager import PowerProfileManager


class EnergyManager:
    """
    Główna klasa zarządzająca energią w systemie mikrosieciowym.

    Klasa ta odpowiada za monitorowanie i zarządzanie bilansem energetycznym,
    obsługując zarówno nadwyżki, jak i deficyty energii. Wykorzystuje ona
    osobne menedżery do obsługi nadwyżek (EnergySurplusManager) i deficytów
    (EnergyDeficitManager).

    Attributes:
        microgrid (Microgrid): Obiekt reprezentujący mikrosieć.
        consumergrid (EnergyConsumerGrid): Obiekt reprezentujący sieć konsumentów.
        osd (OSD): Obiekt reprezentujący operatora systemu dystrybucyjnego.
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
        self.first_run = True
        self.initial_data_path = "C:/eryk/AppFuga/apps/backend/initial_data.json"
        self.initial_contract_path = "C:/eryk/AppFuga/apps/backend/contract_data.json"
        self.live_data_path = "C:/eryk/AppFuga/apps/backend/live_data.json"
        self.live_contract_path = "C:/eryk/AppFuga/apps/backend/live_contract_data.json"
        self.power_profile_manager = PowerProfileManager(
            "C:/eryk/AppFuga/apps/backend/power_profile",
            self.info_logger,
            self.error_logger,
        )
        self.info_logger.info("####################PowerProfileManager initialized")

    def start(self):
        """Uruchamia proces zarządzania energią w osobnym wątku."""
        self.running = True
        self.stop_event.clear()
        Thread(target=self.run_energy_management).start()
        self.info_logger.info("Energy management started")

    def stop(self):
        """Zatrzymuje proces zarządzania energią."""
        self.running = False
        self.stop_event.set()
        self.info_logger.info("Energy management stopping")

    def run_energy_management(self):
        """Główna pętla zarządzania energią."""
        while self.running and not self.stop_event.is_set():
            try:
                if self.first_run:
                    self.load_initial_data()
                    self.first_run = False
                else:
                    self.load_live_data()

                self.run_single_iteration()
                self.save_live_data()
                self.save_contract_data()
                self.info_logger.info(
                    f"Waiting {self.restart_delay} seconds before next iteration..."
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

        if self.osd is None:
            self.error_logger.error(
                "OSD object is None. Cannot proceed with the iteration."
            )
            return
        microgrid_data = self.prepare_microgrid_data()
        microgrid_errors = DataValidator.validate_microgrid_data(microgrid_data)
        osd_errors = DataValidator.validate_contract_data(self.osd.__dict__)

        if microgrid_errors or osd_errors:
            self.handle_validation_errors(microgrid_errors, osd_errors)
            return

        self.info_logger.info("Starting device update based on meter readings")
        updated_devices = self.microgrid.update_device_with_meter_data()
        if updated_devices:
            self.info_logger.info(
                f"Updated {len(updated_devices)} devices based on meter readings"
            )
            for device in updated_devices:
                self.info_logger.info(
                    f"Updated device: {device.name} (ID: {device.id}), New status: {device.device_status}, New output: {device.actual_output} kW"
                )
        else:
            self.info_logger.info("No devices were updated based on meter readings")

        if self.osd is None:
            self.error_logger.error(
                "OSD object is None. Cannot proceed with the iteration."
            )
            return

        self.log_system_summary()
        self.update_power_profile()  # funkcja do profilu mocy
        self.check_energy_conditions()

    def prepare_microgrid_data(self):
        """Przygotowuje dane mikrosieci do walidacji."""
        return {
            "pv_panels": [panel.to_dict() for panel in self.microgrid.pv_panels],
            "wind_turbines": [
                turbine.to_dict() for turbine in self.microgrid.wind_turbines
            ],
            "fuel_turbines": [
                turbine.to_dict() for turbine in self.microgrid.fuel_turbines
            ],
            "fuel_cells": [cell.to_dict() for cell in self.microgrid.fuel_cells],
            "bess": [self.microgrid.bess.to_dict()] if self.microgrid.bess else [],
            "power_meters": [
                meter.to_dict() for meter in self.microgrid.power_meters.values()
            ],
        }

    def handle_validation_errors(self, microgrid_errors, osd_errors):
        """Obsługuje błędy walidacji danych mikrosieci i OSD."""
        self.error_logger.error("Validation errors detected. Stopping the algorithm.")
        for error in microgrid_errors:
            self.error_logger.error(f"Microgrid validation error: {error}")
        for error in osd_errors:
            self.error_logger.error(f"OSD validation error: {error}")
        self.stop()

    def handle_runtime_error(self, e):
        """Obsługuje błędy wykonania występujące podczas zarządzania energią."""
        self.error_logger.error(f"Error in energy management: {str(e)}")
        self.error_logger.exception("Full traceback:")
        self.error_logger.error("An error occurred. Stopping the algorithm.")
        self.stop()

    def check_energy_conditions(self):
        """Sprawdza warunki energetyczne i inicjuje odpowiednie działania."""
        try:
            total_generated_power = self.microgrid.total_power_generated()
            total_demand_power = self.consumergrid.total_power_consumed()

            if total_generated_power > total_demand_power:
                self.info_logger.info(
                    "Power surplus detected - starting surplus management"
                )
                power_surplus = total_generated_power - total_demand_power
                self.manage_surplus(power_surplus)
            elif total_generated_power < total_demand_power:
                self.info_logger.info(
                    "Power deficit detected - starting deficit management"
                )
                power_deficit = total_demand_power - total_generated_power
                self.manage_deficit(power_deficit)
            else:
                self.info_logger.info(
                    "Power generation matches demand - no action needed"
                )
        except Exception as e:
            self.error_logger.error(f"Error checking energy conditions: {str(e)}")

    def manage_surplus(self, power_surplus):
        """Zarządza nadwyżką energii."""
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
        """Zarządza deficytem energii."""
        result = self.deficit_manager.handle_deficit(power_deficit)
        managed_amount = result["amount_managed"]
        remaining_deficit = result["remaining_deficit"]

        self.info_logger.info(
            f"Managed {managed_amount} kW of deficit. Remaining: {remaining_deficit} kW"
        )

        if remaining_deficit > 0:
            self.info_logger.warning(
                f"Deficit management completed. Remaining unresolved deficit: {remaining_deficit} kW"
            )
        else:
            self.info_logger.info(
                "Deficit management completed. The entire deficit has been resolved."
            )

    def log_system_summary(self):
        """Loguje podsumowanie stanu systemu."""
        total_generated_power = self.microgrid.total_power_generated()
        total_demand_power = self.consumergrid.total_power_consumed()
        active_devices = self.microgrid.get_active_devices()
        inactive_devices = self.microgrid.get_inactive_devices()

        summary = [
            "System status summary:",
            f"Total generated power: {total_generated_power} kW",
            f"Total demand: {total_demand_power} kW",
            f"Number of active generating devices: {len(active_devices)}",
            f"Number of inactive generating devices: {len(inactive_devices)}",
        ]

        if active_devices:
            summary.append("Active generating devices:")
            for device in active_devices:
                summary.append(
                    f"  - {device.name}: {device.get_actual_output()} kW / {device.get_max_output()} kW"
                )

        if inactive_devices:
            summary.append("Inactive generating devices:")
            for device in inactive_devices:
                summary.append(
                    f"  - {device.name}: max output {device.get_max_output()} kW"
                )

        if self.microgrid.bess:
            bess = self.microgrid.bess
            summary.append(
                f"BESS charge level: {bess.get_charge_level()} kWh / {bess.get_capacity()} kWh"
            )

        summary.extend(
            [
                f"Energy purchase: {'Available' if self.osd.can_buy_energy() else 'Not available'} (Limit: {self.osd.get_purchase_limit()} kWh, Current: {self.osd.get_bought_power()} kWh)",
                f"Energy sale: {'Available' if self.osd.can_sell_energy() else 'Not available'} (Limit: {self.osd.get_sale_limit()} kWh, Current: {self.osd.get_sold_power()} kWh)",
            ]
        )

        for line in summary:
            self.info_logger.info(line)

    def load_initial_data(self):
        self.microgrid.load_data_from_json(self.initial_data_path)
        self.consumergrid.load_data_from_json(self.initial_data_path)
        self.osd = OSD.load_data_from_json(self.initial_contract_path)
        if self.osd is None:
            raise ValueError("Failed to load OSD data from initial contract file.")
        self.surplus_manager.osd = self.osd
        self.deficit_manager.osd = self.osd
        self.info_logger.info("Loaded initial data")

    def load_live_data(self):
        try:
            self.microgrid.load_data_from_json(self.live_data_path)
            self.consumergrid.load_data_from_json(self.live_data_path)
            new_osd = OSD.load_data_from_json(self.live_contract_path)
            if new_osd is not None:
                self.osd = new_osd
                self.surplus_manager.osd = self.osd
                self.deficit_manager.osd = self.osd
            else:
                raise ValueError("Failed to load OSD data from live contract file.")
            self.info_logger.info("Loaded live data")
        except FileNotFoundError:
            self.error_logger.error("Live data files not found. Loading initial data.")
            self.load_initial_data()

    def save_live_data(self):
        """Generuje i zapisuje aktualny stan wszystkich urządzeń do pliku JSON."""
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

        with open(self.live_data_path, "w") as f:
            json.dump(live_data, f, indent=4)

        self.info_logger.info("Live data saved to live_data.json")

    def save_contract_data(self):
        """Generuje i zapisuje aktualne dane kontraktowe do osobnego pliku JSON."""

        contract_data = {
            "CONTRACTED_TYPE": self.osd.CONTRACTED_TYPE,
            "CONTRACTED_DURATION": self.osd.CONTRACTED_DURATION,
            "CONTRACTED_MARGIN": self.osd.CONTRACTED_MARGIN,
            "CONTRACTED_EXPORT_POSSIBILITY": self.osd.CONTRACTED_EXPORT_POSSIBILITY,
            "CONTRACTED_SALE_LIMIT": self.osd.CONTRACTED_SALE_LIMIT,
            "CONTRACTED_PURCHASE_LIMIT": self.osd.CONTRACTED_PURCHASE_LIMIT,
            "sold_power": self.osd.get_sold_power(),
            "bought_power": self.osd.get_bought_power(),
            "current_tariff_buy": self.osd.get_current_buy_price(),
            "current_tariff_sell": self.osd.get_current_sell_price(),
        }

        with open(self.live_contract_path, "w") as f:
            json.dump(contract_data, f, indent=4)

        self.info_logger.info("Live contract data saved to live_contract_data.json")

    def update_power_profile(self):
        self.info_logger.info("###############Updating power profile in EnergyManager")
        current_time = datetime.now()
        consumption = self.consumergrid.total_power_consumed()
        generation = self.microgrid.total_power_generated()
        buy_price = self.osd.get_current_buy_price()
        sell_price = self.osd.get_current_sell_price()

        self.power_profile_manager.update(
            current_time, consumption, generation, buy_price, sell_price
        )
