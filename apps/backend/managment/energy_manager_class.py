from collections import defaultdict
from datetime import datetime
import json
import os
import random
from threading import Thread, Event
import time
import uuid
from apps.backend.devices.bess_class import BESS
from apps.backend.managment.energy_surplus_manager_class import EnergySurplusManager
from apps.backend.managment.energy_deficit_manager_class import EnergyDeficitManager
from apps.backend.others.osd_class import OSD
from apps.backend.others.data_validator import DataValidator
from apps.backend.managment.power_profile_manager import PowerProfileManager
from apps.backend.managment.operation_action import OperationMode
from apps.backend.managment.surplus_action import SurplusAction
from apps.backend.devices.pv_class import PV
from apps.backend.devices.wind_turbine_class import WindTurbine
from apps.backend.devices.fuel_cell_class import FuelCell
from apps.backend.devices.fuel_turbine_class import FuelTurbine
from apps.backend.devices.adjustable_devices import AdjustableDevice


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
            microgrid,
            osd,
            info_logger,
            error_logger,
            self.execute_action,
            self.add_to_tabu_list,
            self.is_in_tabu_list,
            self.clean_tabu_list,
        )
        self.deficit_manager = EnergyDeficitManager(
            microgrid,
            consumergrid,
            osd,
            info_logger,
            error_logger,
            self.execute_action,
            self.add_to_tabu_list,
            self.is_in_tabu_list,
            self.clean_tabu_list,
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
            api_key="708e75906d18e5338d7f573cf9c01041",
            lat=50.86,
            lon=16.32,
        )
        self.auto_interval = 30  # 30 sekund dla trybu automatycznego
        self.semi_auto_interval = 15  # 5 minut dla trybu półautomatycznego
        self.operation_mode = OperationMode.AUTOMATIC
        self.action_timeout = 60  # 1 minuta na decyzję operatora
        self.pending_actions_path = os.path.join(
            os.path.dirname(__file__),
            "C:/eryk/AppFuga/apps/backend/pending_actions.json",
        )
        self.operator_decisions_path = os.path.join(
            os.path.dirname(__file__),
            "C:/eryk/AppFuga/apps/backend/operator_decisions.json",
        )
        self.operator_actions = {"pending_actions": [], "completed_actions": []}
        self.EPSILON = 1e-6  # Dodaj tę linię
        self.tabu_list = {}
        self.tabu_duration = 25  # 5 minut w sekundach
        self.last_tabu_clean = time.time()
        self.tabu_clean_interval = 60  # Czyść listę co minutę

    def load_configuration(self):
        try:
            with open(
                "C:/eryk/AppFuga/apps/backend/operation_mode.json", "r"
            ) as mode_file:
                mode_data = json.load(mode_file)
                self.operation_mode = OperationMode(mode_data.get("mode", "automatic"))
            self.info_logger.info(f"Loaded operation mode: {self.operation_mode.value}")
        except Exception as e:
            self.error_logger.error(f"Error loading configuration: {str(e)}")
            self.operation_mode = OperationMode.AUTOMATIC

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
        self.first_run = True
        while self.running and not self.stop_event.is_set():
            try:
                self.load_configuration()
                if self.first_run:
                    self.load_initial_data()
                    self.first_run = False
                else:
                    self.load_live_data()

                result = self.run_single_iteration()
                wait_time = (
                    self.auto_interval
                    if self.operation_mode == OperationMode.AUTOMATIC
                    else self.semi_auto_interval
                )
                self.info_logger.info(f"Waiting {wait_time} seconds for next iteration")
                if self.stop_event.wait(wait_time):
                    break
            except Exception as e:
                self.handle_runtime_error(e)
                break
        self.info_logger.info("Energy management stopped")

    def run_single_iteration(self):
        self.info_logger.info(
            f"Starting a new iteration in {self.operation_mode.value} mode"
        )
        start_time = time.time()

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
        self.log_system_summary()
        self.info_logger.info(
            f"BESS charge level before actions: {self.microgrid.bess.get_charge_level():.2f} kWh"
        )

        result = self.check_energy_conditions()

        approved_actions = []
        if result is not None:
            if "approved_actions" in result:
                approved_actions = result["approved_actions"]

        # Wykonaj zatwierdzone akcje tylko raz
        if approved_actions:
            self.execute_approved_actions(approved_actions)

        self.log_system_summary()
        self.save_live_data()
        self.save_contract_data()
        self.update_power_profile(datetime.now())

        elapsed_time = time.time() - start_time
        self.info_logger.info(f"Iteration completed in {elapsed_time:.2f} seconds")
        self.info_logger.info(
            f"BESS charge level after actions: {self.microgrid.bess.get_charge_level():.2f} kWh"
        )

        return result

    def calculate_current_surplus(self):
        try:
            total_generated_power = self.microgrid.total_power_generated()
            total_demand_power = self.consumergrid.total_power_consumed()
            surplus = max(0, total_generated_power - total_demand_power)
            self.info_logger.info(f"Recalculated surplus: {surplus} kW")
            return surplus
        except Exception as e:
            self.error_logger.error(f"Error calculating current surplus: {str(e)}")
            return None

    def clean_up_expired_actions(self):
        actions = self.load_operator_actions()
        current_time = time.time()
        new_pending_actions = []
        for action in actions["pending_actions"]:
            if current_time - action["timestamp"] > self.action_timeout:
                self.info_logger.info(
                    f"Action expired: {action['device_name']} - {action['action']}"
                )
                action["status"] = "expired"
                actions["completed_actions"].append(action)
            else:
                new_pending_actions.append(action)
        actions["pending_actions"] = new_pending_actions
        self.save_operator_actions(actions)

    def wait_for_operator_decision(self, action):
        start_time = time.time()
        while time.time() - start_time < self.action_timeout:
            decision = self.load_operator_decision()
            if decision:
                return decision.get("approved", False)
            time.sleep(1)  # Krótka przerwa, aby nie obciążać CPU
        return False  # Timeout - traktujemy jako odmowę

    def execute_action(self, device, action):
        self.info_logger.info(
            f"EnergyManager.execute_action called with device: {device.name}, action: {action}"
        )
        if self.operation_mode == OperationMode.AUTOMATIC:
            return self.perform_action(device, action)
        else:
            serializable_action = {
                "device_id": device.id,
                "device_name": device.name,
                "action": action,
                "timestamp": int(time.time()),
            }
            self.add_pending_action(serializable_action)
            # Zwracamy informację o oczekującej akcji
            return {
                "pending": True,
                "success": True,
                "amount": self.get_action_amount(action),
            }

    def get_action_amount(self, action):
        if action.startswith("charge:"):
            _, amount = action.split(":")
            return float(amount)
        elif action.startswith("sell:"):
            _, amount = action.split(":")
            return float(amount)
        elif action.startswith("set_output:"):
            _, new_output = action.split(":")
            return float(new_output)
        else:
            return 0

    def add_pending_action(self, action):
        """
        Dodaje akcję do listy oczekujących akcji.

        :param action: Słownik reprezentujący akcję do dodania
        """
        actions = self.load_pending_actions()
        actions.append(action)
        self.save_pending_actions(actions)

    def remove_pending_action(self, action):
        try:
            actions = self.load_pending_actions()
            actions = [a for a in actions if a.get("id") != action.get("id")]
            self.save_pending_actions(actions)
        except Exception as e:
            self.error_logger.exception(f"Error in remove_pending_action: {str(e)}")

    def load_pending_actions(self):
        try:
            with open(self.pending_actions_path, "r") as file:
                return json.load(file)
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def save_pending_actions(self, actions):
        with open(self.pending_actions_path, "w") as f:
            json.dump(actions, f, indent=2)
        self.info_logger.info(f"Saved {len(actions)} pending actions")
        for action in actions:
            self.info_logger.info(f"Pending action: {json.dumps(action, indent=2)}")

        # Weryfikacja zapisu
        self.verify_file_content(self.pending_actions_path, "pending actions")

    def load_operator_decision(self):
        try:
            with open(self.operator_decisions_path, "r") as file:
                decisions = json.load(file)
                return decisions[0] if decisions else None
        except (FileNotFoundError, json.JSONDecodeError):
            return None

    def save_operator_decisions(self, decisions):
        with open(self.operator_decisions_path, "w") as f:
            json.dump(decisions, f, indent=2)
        self.info_logger.info(f"Saved {len(decisions)} operator decisions")
        for decision in decisions:
            self.info_logger.info(
                f"Operator decision: {json.dumps(decision, indent=2)}"
            )

        # Weryfikacja zapisu
        self.verify_file_content(self.operator_decisions_path, "operator decisions")

    def verify_file_content(self, file_path, file_description):
        try:
            with open(file_path, "r") as f:
                content = json.load(f)
            self.info_logger.info(
                f"Successfully verified {file_description} file. Content: {json.dumps(content, indent=2)}"
            )
        except Exception as e:
            self.error_logger.error(
                f"Error verifying {file_description} file: {str(e)}"
            )

    def process_pending_actions(self):
        actions = self.load_operator_actions()
        new_pending_actions = []
        for action in actions["pending_actions"]:
            if action["status"] == "approved":
                device = self.microgrid.get_device_by_id(action["device_id"])
                if device:
                    result = self.perform_action(device, action["action"])
                    if result["success"]:
                        self.info_logger.info(
                            f"Processed approved action: {action['device_name']} - {action['action']}"
                        )
                    else:
                        self.error_logger.error(
                            f"Failed to process approved action: {action['device_name']} - {action['action']}"
                        )
                else:
                    self.error_logger.error(f"Device not found for action: {action}")
            elif action["status"] == "rejected":
                self.info_logger.info(
                    f"Action rejected: {action['device_name']} - {action['action']}"
                )
            else:
                new_pending_actions.append(action)
        actions["pending_actions"] = new_pending_actions
        self.save_operator_actions(actions)

    def perform_action(self, device, action):
        device_name = self.get_device_name(device)
        self.info_logger.info(f"Performing action: {device_name} - {action}")

        try:
            if action.startswith("charge:"):
                _, amount = action.split(":")
                return self.surplus_manager.decide_to_charge_bess(float(amount))
            elif action.startswith("sell:"):
                _, amount = action.split(":")
                return self.surplus_manager.decide_to_sell_energy(float(amount))
            elif action.startswith("set_output:"):
                _, value = action.split(":")
                new_output = float(value)
                if isinstance(device, BESS):
                    self.error_logger.error(
                        f"Cannot set output for BESS device: {device_name}"
                    )
                    return {
                        "success": False,
                        "amount": 0,
                        "reason": "Cannot set output for BESS",
                    }
                current_output = device.get_actual_output()
                success = device.set_output(new_output)
                if success:
                    actual_new_output = device.get_actual_output()
                    reduction = current_output - actual_new_output
                    self.info_logger.info(
                        f"Set output for {device_name} from {current_output} kW to {actual_new_output} kW"
                    )
                    return {"success": True, "amount": reduction}
                else:
                    return {
                        "success": False,
                        "amount": 0,
                        "reason": f"Failed to set output for {device_name}",
                    }
            elif action.startswith("increase:"):
                _, amount = action.split(":")
                amount = float(amount)
                current_output = device.get_actual_output()
                new_output = min(current_output + amount, device.get_max_output())
                success = device.set_output(new_output)
                if success:
                    actual_increase = new_output - current_output
                    self.info_logger.info(
                        f"Increased output of {device_name} from {current_output} kW to {new_output} kW"
                    )
                    return {"success": True, "amount": actual_increase}
                else:
                    return {
                        "success": False,
                        "amount": 0,
                        "reason": f"Failed to increase output for {device_name}",
                    }
            elif action.startswith("activate:"):
                _, amount = action.split(":")
                amount = float(amount)
                if device.try_activate():
                    new_output = min(amount, device.get_max_output())
                    success = device.set_output(new_output)
                    if success:
                        self.info_logger.info(
                            f"Activated {device_name} and set output to {new_output} kW"
                        )
                        return {"success": True, "amount": new_output}
                    else:
                        return {
                            "success": False,
                            "amount": 0,
                            "reason": f"Failed to set output for {device_name} after activation",
                        }
                else:
                    return {
                        "success": False,
                        "amount": 0,
                        "reason": f"Failed to activate {device_name}",
                    }
            elif action.startswith("discharge:"):
                _, amount = action.split(":")
                amount = float(amount)
                if isinstance(device, BESS):
                    discharged = device.try_discharge(amount)
                    if discharged is not None:
                        percent_discharged, amount_discharged = discharged
                        self.info_logger.info(
                            f"BESS discharged by {amount_discharged} kWh"
                        )
                        return {"success": True, "amount": amount_discharged}
                    else:
                        return {
                            "success": False,
                            "amount": 0,
                            "reason": "Failed to discharge BESS",
                        }
                else:
                    return {
                        "success": False,
                        "amount": 0,
                        "reason": "Device is not BESS",
                    }
            elif action.startswith("buy:"):
                _, amount = action.split(":")
                amount = float(amount)
                return self.deficit_manager.buy_energy(amount)
            elif action.startswith("reduce:"):
                _, amount = action.split(":")
                amount = float(amount)
                if isinstance(device, AdjustableDevice):
                    actual_reduction = device.decrease_power(amount)
                    return {"success": True, "amount": actual_reduction}
                else:
                    return {
                        "success": False,
                        "amount": 0,
                        "reason": f"Cannot reduce power for non-adjustable device {device_name}",
                    }
            elif action == "deactivate":
                if device.deactivate():
                    return {"success": True, "amount": device.power}
                else:
                    return {
                        "success": False,
                        "amount": 0,
                        "reason": f"Failed to deactivate {device_name}",
                    }
            else:
                self.error_logger.error(f"Unknown action: {action}")
                return {
                    "success": False,
                    "amount": 0,
                    "reason": f"Unknown action: {action}",
                }
        except Exception as e:
            self.error_logger.exception(f"Error in perform_action: {str(e)}")
            return {"success": False, "amount": 0, "reason": str(e)}

    def process_operator_decisions(self):
        decisions = self.load_operator_decisions()
        pending_actions = self.load_pending_actions()

        for decision in decisions:
            if decision["approved"]:
                device = self.microgrid.get_device_by_id(decision["device_id"])
                if device:
                    result = self.perform_action(device, decision["action"])
                    self.info_logger.info(
                        f"Processed approved action: {decision['device_name']} - {decision['action']}, Result: {result}"
                    )
                else:
                    self.error_logger.error(f"Device not found for action: {decision}")

        # Usuń przetworzone akcje z pending_actions
        pending_actions = [
            action
            for action in pending_actions
            if not any(
                d["device_id"] == action["device_id"]
                and d["action"] == action["action"]
                for d in decisions
            )
        ]

        self.save_pending_actions(pending_actions)
        self.save_operator_decisions([])  # Czyścimy decyzje po przetworzeniu

    def process_completed_action(self, action):
        if action["status"] == "approved":
            device = self.microgrid.get_device_by_id(action["device_id"])
            if device:
                self.perform_action(device, action["action"])
        action["decision_timestamp"] = int(time.time())
        self.operator_actions["completed_actions"].append(action)

    def load_operator_actions(self):
        try:
            with open(self.operator_actions_path, "r") as file:
                actions = json.load(file)
            return actions
        except FileNotFoundError:
            self.info_logger.warning(
                f"operator_actions.json not found at {self.operator_actions_path}. Creating new file."
            )
            actions = {"pending_actions": [], "completed_actions": []}
            self.save_operator_actions(actions)
            return actions
        except json.JSONDecodeError:
            self.error_logger.error(
                f"Error decoding operator_actions.json. File may be corrupted."
            )
            return {"pending_actions": [], "completed_actions": []}

    def save_operator_actions(self, actions):
        with open(self.operator_actions_path, "w") as file:
            json.dump(actions, file, indent=2)

    def check_operator_decisions(self):
        try:
            with open(self.operator_decisions_path, "r") as file:
                decisions = json.load(file)
            # Symulacja: zawsze zwracamy pozytywną decyzję
            return [{**action, "approved": True} for action in decisions]
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def process_approved_action(self, action):
        device = self.microgrid.get_device_by_id(action["device_id"])
        if device:
            result = self.perform_action(device, action["action"])
            if result["success"]:
                self.info_logger.info(
                    f"Action executed successfully: {action['device_name']} - {action['action']}"
                )
            else:
                self.error_logger.error(
                    f"Action execution failed: {action['device_name']} - {action['action']} - {result.get('error')}"
                )
        else:
            self.error_logger.error(f"Device not found for action: {action}")

    #############################################

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

    def check_energy_conditions(self):
        try:
            total_generated_power = self.microgrid.total_power_generated()
            total_demand_power = self.consumergrid.total_power_consumed()

            self.info_logger.info(f"Total generated power: {total_generated_power} kW")
            self.info_logger.info(f"Total demand power: {total_demand_power} kW")

            result = None
            if total_generated_power > total_demand_power:
                power_surplus = total_generated_power - total_demand_power
                self.info_logger.info(
                    f"Power surplus detected: {power_surplus} kW - starting surplus management"
                )
                result = self.manage_surplus(power_surplus)
            elif total_generated_power < total_demand_power:
                power_deficit = total_demand_power - total_generated_power
                self.info_logger.info(
                    f"Power deficit detected: {power_deficit} kW - starting deficit management"
                )
                result = self.manage_deficit(power_deficit)
            else:
                self.info_logger.info(
                    "Power generation matches demand - no action needed"
                )

            return result
        except Exception as e:
            self.error_logger.error(f"Error checking energy conditions: {str(e)}")
            return None

    def manage_surplus(self, power_surplus):
        if self.operation_mode == OperationMode.AUTOMATIC:
            return self.manage_surplus_automatic(power_surplus)
        else:
            return self.manage_surplus_semi_automatic(power_surplus)

    def manage_surplus_automatic(self, power_surplus):
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

    def manage_deficit_automatic(self, power_deficit):
        result = self.deficit_manager.handle_deficit_automatic(power_deficit)
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

        return result

    def manage_surplus_semi_automatic(self, power_surplus):
        self.info_logger.info(
            f"Managing surplus in semi-automatic mode: {power_surplus} kW"
        )
        self.log_tabu_list()  # Dodaj tę linię
        self.clean_tabu_list()

        # Użyj surplus_manager do wywołania get_proposed_actions
        all_actions = self.surplus_manager.get_proposed_actions(power_surplus)
        filtered_actions = [
            action
            for action in all_actions
            if not self.is_in_tabu_list(action["device_id"])
        ]

        self.info_logger.info(
            f"Generated {len(all_actions)} possible actions, {len(filtered_actions)} after tabu list filter"
        )
        self.save_pending_actions(filtered_actions)

        operator_decisions = self.generate_operator_decisions(filtered_actions)
        self.save_operator_decisions(operator_decisions)

        approved_actions = []
        remaining_surplus = power_surplus

        for action, decision in zip(filtered_actions, operator_decisions):
            if decision["approved"]:
                approved_actions.append(action)
                remaining_surplus -= action["reduction"]
                self.info_logger.info(
                    f"Action approved: {json.dumps(action, indent=2)}"
                )
            else:
                self.info_logger.info(
                    f"Action rejected: {json.dumps(action, indent=2)}"
                )
                self.add_to_tabu_list(action["device_id"])

        self.clear_pending_actions()
        self.clear_operator_decisions()

        self.info_logger.info(
            f"Surplus management completed. Approved actions: {len(approved_actions)}, "
            f"Initial surplus: {power_surplus} kW, Remaining surplus: {remaining_surplus} kW, "
            f"Current tabu list size: {len(self.tabu_list)}"
        )
        return {
            "approved_actions": approved_actions,
            "initial_surplus": power_surplus,
            "remaining_surplus": remaining_surplus,
        }

    def manage_deficit_semi_automatic(self, power_deficit):
        self.info_logger.info(
            f"Managing deficit in semi-automatic mode: {power_deficit} kW"
        )
        self.log_tabu_list()
        self.clean_tabu_list()

        all_actions = self.deficit_manager.get_proposed_actions(power_deficit)
        filtered_actions = [
            action
            for action in all_actions
            if not self.is_in_tabu_list(action["device_id"])
        ]

        self.info_logger.info(
            f"Generated {len(all_actions)} possible actions, {len(filtered_actions)} after tabu list filter"
        )
        self.save_pending_actions(filtered_actions)

        operator_decisions = self.generate_operator_decisions(filtered_actions)
        self.save_operator_decisions(operator_decisions)

        approved_actions = []
        remaining_deficit = power_deficit

        for action, decision in zip(filtered_actions, operator_decisions):
            if decision["approved"]:
                approved_actions.append(action)
                remaining_deficit -= action["reduction"]
                self.info_logger.info(
                    f"Action approved: {json.dumps(action, indent=2)}"
                )
            else:
                self.info_logger.info(
                    f"Action rejected: {json.dumps(action, indent=2)}"
                )
                self.add_to_tabu_list(action["device_id"])

        self.clear_pending_actions()
        self.clear_operator_decisions()

        self.info_logger.info(
            f"Deficit management completed. Approved actions: {len(approved_actions)}, "
            f"Initial deficit: {power_deficit} kW, Remaining deficit: {remaining_deficit} kW, "
            f"Current tabu list size: {len(self.tabu_list)}"
        )
        return {
            "approved_actions": approved_actions,
            "initial_deficit": power_deficit,
            "remaining_deficit": remaining_deficit,
        }

    def clear_pending_actions(self):
        with open(self.pending_actions_path, "w") as f:
            json.dump([], f)
        self.info_logger.info("Cleared pending actions file")
        self.verify_file_content(self.pending_actions_path, "cleared pending actions")

    def generate_operator_decisions(self, actions):
        decisions = [
            {"approved": random.choice([True, True]), "action_id": action["id"]}
            for action in actions
        ]
        self.info_logger.info("Generated operator decisions:")
        for decision in decisions:
            self.info_logger.info(f"Decision: {json.dumps(decision, indent=2)}")
        return decisions

    def get_available_actions(self, bess_available, export_possible, attempted_actions):
        available_actions = []
        if (
            bess_available
            and export_possible
            and SurplusAction.BOTH not in attempted_actions
        ):
            available_actions.append(SurplusAction.BOTH)
        if bess_available and SurplusAction.CHARGE_BATTERY not in attempted_actions:
            available_actions.append(SurplusAction.CHARGE_BATTERY)
        if export_possible and SurplusAction.SELL_ENERGY not in attempted_actions:
            available_actions.append(SurplusAction.SELL_ENERGY)
        if SurplusAction.LIMIT_GENERATION not in attempted_actions:
            available_actions.append(SurplusAction.LIMIT_GENERATION)
        return available_actions

    def prepare_serializable_action(self, action):
        return {
            "id": str(uuid.uuid4()),
            "device_id": (
                action["device"].id if hasattr(action["device"], "id") else "OSD"
            ),
            "device_name": (
                action["device"].name if hasattr(action["device"], "name") else "OSD"
            ),
            "device_type": self.get_device_type(action["device"]),
            "action": action["action"],
            "current_output": action.get("current_output"),
            "proposed_output": action.get("proposed_output"),
            "reduction": action.get("reduction"),
            "timestamp": int(time.time()),
        }

    def simulate_operator_decision(self, action):
        # Symulacja decyzji operatora
        decision = random.choice([True, True])
        self.info_logger.info(
            f"Simulated operator decision for {action['device_name']}: {'Approved' if decision else 'Rejected'}"
        )
        return decision

    def manage_deficit(self, power_deficit):
        if self.operation_mode == OperationMode.AUTOMATIC:
            return self.manage_deficit_automatic(power_deficit)
        else:
            return self.manage_deficit_semi_automatic(power_deficit)

    def clear_operator_decision(self):
        with open(self.operator_decisions_path, "w") as file:
            json.dump([], file)

    def clear_operator_decisions(self):
        with open(self.operator_decisions_path, "w") as f:
            json.dump([], f)
        self.info_logger.info("Cleared operator decisions file")
        self.verify_file_content(
            self.operator_decisions_path, "cleared operator decisions"
        )

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

    def log_system_summary(self):
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

    def update_power_profile(self, current_time):
        consumption = self.consumergrid.total_power_consumed()
        generation = self.microgrid.total_power_generated()
        buy_price = self.osd.get_current_buy_price()
        sell_price = self.osd.get_current_sell_price()

        self.power_profile_manager.update(
            current_time, consumption, generation, buy_price, sell_price
        )

    def execute_approved_action(self, action):
        self.info_logger.info(
            f"Executing approved action: {action['action']} for {action['device_name']}"
        )
        device = self.get_device_by_id_and_type(
            action["device_id"], action["device_type"]
        )
        if device:
            result = self.perform_action(device, action["action"])
            if result["success"]:
                self.info_logger.info(
                    f"Action executed to reduce {result['amount']:.2f} kW."
                )
                return {"success": True, "amount": result["amount"]}
            else:
                self.info_logger.warning(
                    f"Action execution failed: {result.get('reason', 'Unknown reason')}"
                )
        else:
            self.error_logger.error(f"Device not found for action: {action}")
        return {"success": False, "amount": 0}

    def get_device_by_id_and_type(self, device_id, device_type):
        self.info_logger.info(
            f"Searching for device with ID: {device_id}, type: {device_type}"
        )
        if device_type == "OSD":
            return self.osd
        if device_type == "BESS":
            return (
                self.microgrid.bess
                if self.microgrid.bess and self.microgrid.bess.id == device_id
                else None
            )

        device_lists = {
            "PV": self.microgrid.pv_panels,
            "PVPanel": self.microgrid.pv_panels,
            "WindTurbine": self.microgrid.wind_turbines,
            "FuelTurbine": self.microgrid.fuel_turbines,
            "FuelCell": self.microgrid.fuel_cells,
            "AdjustableDevice": self.consumergrid.adjustable_devices,
            "NonAdjustableDevice": self.consumergrid.non_adjustable_devices,
        }

        if device_type in device_lists:
            for device in device_lists[device_type]:
                if device.id == device_id:
                    self.info_logger.info(f"Found device: {device.name}")
                    return device
        else:
            self.error_logger.error(f"Unknown device type: {device_type}")

        self.error_logger.error(f"Device not found: ID {device_id}, type {device_type}")
        return None

    def execute_approved_actions(self, approved_actions):
        self.info_logger.info("Executing approved actions:")
        for action in approved_actions:
            self.info_logger.info(f"Processing action: {action}")
            if action.get("executed", False):
                self.info_logger.info(
                    f"Action already executed: {action['action']} for {action['device_name']}"
                )
                continue

            device = self.get_device_by_id_and_type(
                action["device_id"], action["device_type"]
            )
            if device:
                device_name = self.get_device_name(device)
                device_type = type(device).__name__
                self.info_logger.info(
                    f"Device found: {device_name}, type: {device_type}"
                )

                if isinstance(device, BESS):
                    self.info_logger.info(
                        f"Before action: {device_name} charge level: {device.get_charge_level()} kWh"
                    )
                elif isinstance(device, OSD):
                    self.info_logger.info(
                        f"Before action: OSD current sold power: {device.get_sold_power()} kW"
                    )
                else:
                    self.info_logger.info(
                        f"Before action: {device_name} output: {device.get_actual_output()} kW"
                    )

                result = self.perform_action(device, action["action"])

                if result["success"]:
                    if isinstance(device, BESS):
                        self.info_logger.info(
                            f"After action: {device_name} charge level: {device.get_charge_level()} kWh"
                        )
                        self.info_logger.info(
                            f"Executed {action['action']} for {device_name}: Success. New charge level: {device.get_charge_level()} kWh"
                        )
                    elif isinstance(device, OSD):
                        self.info_logger.info(
                            f"After action: OSD new sold power: {device.get_sold_power()} kW"
                        )
                        self.info_logger.info(
                            f"Executed {action['action']} for OSD: Success. Amount sold: {result['amount']} kW"
                        )
                    else:
                        new_output = device.get_actual_output()
                        self.info_logger.info(
                            f"After action: {device_name} output: {new_output} kW"
                        )
                        self.info_logger.info(
                            f"Executed {action['action']} for {device_name}: Success. New output: {new_output} kW"
                        )
                else:
                    self.error_logger.error(
                        f"Failed to execute action {action['action']} for {device_name}: {result.get('reason', 'Unknown reason')}"
                    )
            else:
                self.error_logger.error(f"Device not found for action: {action}")

        self.log_system_summary()

    def get_device_name(self, device):
        if isinstance(device, OSD):
            return "OSD"
        elif hasattr(device, "name"):
            return device.name
        else:
            return type(device).__name__

    def get_device_by_id_and_type(self, device_id, device_type):
        self.info_logger.info(
            f"Searching for device with ID: {device_id}, type: {device_type}"
        )
        if device_type == "OSD":
            return self.osd
        if device_type == "BESS":
            return (
                self.microgrid.bess
                if self.microgrid.bess and self.microgrid.bess.id == device_id
                else None
            )

        device_lists = {
            "PV": self.microgrid.pv_panels,
            "PVPanel": self.microgrid.pv_panels,
            "WindTurbine": self.microgrid.wind_turbines,
            "FuelTurbine": self.microgrid.fuel_turbines,
            "FuelCell": self.microgrid.fuel_cells,
        }

        if device_type in device_lists:
            for device in device_lists[device_type]:
                if device.id == device_id:
                    self.info_logger.info(f"Found device: {device.name}")
                    return device
        else:
            self.error_logger.error(f"Unknown device type: {device_type}")

        self.error_logger.error(f"Device not found: ID {device_id}, type {device_type}")
        return None

    def get_device_type(self, device):
        if isinstance(device, PV):
            return "PV"
        elif isinstance(device, WindTurbine):
            return "WindTurbine"
        elif isinstance(device, FuelTurbine):
            return "FuelTurbine"
        elif isinstance(device, FuelCell):
            return "FuelCell"
        elif isinstance(device, BESS):
            return "BESS"
        elif isinstance(device, OSD):
            return "OSD"
        else:
            return type(device).__name__

    def add_to_tabu_list(self, device_id):
        self.tabu_list[str(device_id)] = time.time() + self.tabu_duration
        self.info_logger.info(
            f"#######Added device {device_id} to tabu list. Current list: {self.tabu_list}"
        )

    def is_in_tabu_list(self, device_id):
        self.info_logger.info(
            f"#######Checking if {device_id} is in tabu list: {self.tabu_list}"
        )
        if str(device_id) in self.tabu_list:
            if time.time() < self.tabu_list[str(device_id)]:
                return True
            else:
                del self.tabu_list[str(device_id)]
        return False

    def clean_tabu_list(self):
        current_time = time.time()
        if current_time - self.last_tabu_clean >= self.tabu_clean_interval:
            expired = [
                device_id
                for device_id, expiry_time in self.tabu_list.items()
                if current_time >= expiry_time
            ]
            for device_id in expired:
                del self.tabu_list[device_id]
            self.info_logger.info(
                f"#################Cleaned tabu list. Removed {len(expired)} devices"
            )
            self.last_tabu_clean = current_time

    def log_tabu_list(self):
        self.info_logger.info(f"##################Current tabu list: {self.tabu_list}")
