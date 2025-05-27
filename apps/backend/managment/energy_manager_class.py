from collections import defaultdict
from datetime import datetime
import json
import os
import random
from threading import Thread, Event
import time
import uuid

import requests
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
from apps.backend.devices.energy_point_class import EnergyPoint
from apps.backend.devices.energy_source_class import EnergySource
from apps.backend.others.data_consistency_checker import DataConsistencyChecker
from apps.backend.managment.api_manager import ApiManager


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
        self, microgrid, consumergrid, osd, info_logger, error_logger, check_interval=60, api_base_url="http://localhost:5002", use_api=True
    ):
        self.microgrid = microgrid
        self.consumergrid = consumergrid
        self.osd = osd
        self.info_logger = info_logger
        self.error_logger = error_logger
        
        # Inicjalizacja ścieżek do plików w sposób niezależny od środowiska
        self.base_path = self._get_base_path()
        
        # Ścieżki do plików konfiguracyjnych i danych
        self.initial_data_path = os.path.join(self.base_path, "apps", "backend", "initial_data.json")
        self.initial_contract_path = os.path.join(self.base_path, "apps", "backend", "contract_data.json")
        self.live_data_path = os.path.join(self.base_path, "apps", "backend", "live_data.json")
        self.live_contract_path = os.path.join(self.base_path, "apps", "backend", "live_contract_data.json")
        self.pending_actions_path = os.path.join(self.base_path, "apps", "backend", "pending_actions.json")
        self.operator_decisions_path = os.path.join(self.base_path, "apps", "backend", "operator_decisions.json")
        self.operator_actions_path = os.path.join(self.base_path, "apps", "backend", "operator_actions.json")

        self.output_data_path = os.path.join(self.base_path, "apps", "backend", "output_data.json")
        self.output_contract_path = os.path.join(self.base_path, "apps", "backend", "output_contract_data.json")

        self.status_path = os.path.join(self.base_path, "apps", "backend", "system_status.json")
        
        # Inicjalizacja menedżerów
        self.surplus_manager = EnergySurplusManager(
            microgrid,
            osd,
            info_logger,
            error_logger,
            self.execute_action,
            self.add_to_tabu_list,
            self.is_in_tabu_list,
            self.clean_tabu_list,
            energy_manager_ref=self  # ← DODAJ TO
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
            energy_manager_ref=self  # ← DODAJ TO
        )
        
        # Inicjalizacja menedżera profili mocy
        self.power_profile_manager = PowerProfileManager(
            os.path.join(self.base_path, "apps", "backend", "power_profile"),
            self.info_logger,
            self.error_logger,
            api_key="708e75906d18e5338d7f573cf9c01041",
            lat=50.86,
            lon=16.32,
        )


        
        # Reszta inicjalizacji pozostaje bez zmian
        self.check_interval = check_interval
        self.running = False
        self.stop_event = Event()
        self.restart_delay = 30  # czas oczekiwania przed ponownym startem (w sekundach)
        self.first_run = True
        self.auto_interval = 15  # 30 sekund dla trybu automatycznego
        self.semi_auto_interval = 15  # 5 minut dla trybu półautomatycznego
        self.operation_mode = OperationMode.AUTOMATIC
        self.action_timeout = 60  # 1 minuta na decyzję operatora
        self.operator_actions = {"pending_actions": [], "completed_actions": []}
        self.EPSILON = 1e-6
        self.tabu_list = {}
        self.tabu_duration = 25  # 5 minut w sekundach
        self.last_tabu_clean = time.time()
        self.tabu_clean_interval = 60  # Czyść listę co minutę
        self.data_consistency_checker = DataConsistencyChecker(
            self.live_data_path,
            self.live_data_path,  # Tymczasowo używamy tego samego pliku do zapisu i odczytu
            info_logger,
            error_logger,
            max_attempts=3,
            delay=5,
        )
        self.last_saved_data = None

        # Wyświetl informacje o ścieżkach (pomocne przy debugowaniu)
        self.info_logger.info(f"Base path: {self.base_path}")
        self.info_logger.info(f"Initial data path: {self.initial_data_path}")
        self.info_logger.info(f"Initial contract path: {self.initial_contract_path}")

        self.use_api = use_api
    
        # Inicjalizacja ApiManager
        if self.use_api:
            self.api_manager = ApiManager(
                api_base_url=api_base_url,
                info_logger=info_logger,
                error_logger=error_logger,
                verify_ssl=False
            )

        self.info_logger.info(f"Using API: {self.use_api}")

        self.changed_devices = []




    def _get_base_path(self):
        """
        Zwraca bazową ścieżkę projektu, działającą zarówno lokalnie jak i w kontenerze.
        """
        # Sprawdź, czy jesteśmy w kontenerze
        if os.path.exists('/app'):
            return '/app'
        # W przeciwnym razie zakładamy, że jesteśmy w środowisku lokalnym Windows
        return 'C:/eryk/AppFuga'

    def load_configuration(self):
        operation_mode_path = os.path.join(self.base_path, "apps", "backend", "operation_mode.json")
        try:
            with open(operation_mode_path, "r") as mode_file:
                mode_data = json.load(mode_file)
                self.operation_mode = OperationMode(mode_data.get("mode", "automatic"))
                self.info_logger.info(
                    f"Loaded operation mode: {self.operation_mode.value}"
                )
        except Exception as e:
            self.error_logger.error(f"Error loading configuration: {str(e)}")
            self.operation_mode = OperationMode.AUTOMATIC

    def start(self):
        """Uruchamia proces zarządzania energią w osobnym wątku."""
        self.running = True
        self.stop_event.clear()
        Thread(target=self.run_energy_management).start()
        self.info_logger.important("Energy management started")

    def stop(self):
        """Zatrzymuje proces zarządzania energią."""
        self.running = False
        self.stop_event.set()
        self.info_logger.important("Energy management stopping")

    def run_energy_management(self):
        """Uruchamia proces zarządzania energią w osobnym wątku."""
        while self.running and not self.stop_event.is_set():
            try:
                iteration_start_time = time.time()
                
                # Resetuj listę zmian na początku iteracji
                self.reset_changed_devices()
                
                self.info_logger.highlight("Starting new iteration")
                self.load_configuration()

                # 1. Pobieramy dane z API (jeśli używamy API)
                if self.use_api:
                    success = self.api_manager.fetch_and_save_data(
                        self.live_data_path, 
                        self.live_contract_path,
                        self.status_path
                    )
                    if not success:
                        self.error_logger.error("Failed to fetch data from API")
                        
                        # Sprawdź czy system w trybie alarmowym
                        if self.api_manager.system_in_alarm_mode:
                            self.error_logger.critical("System is in ALARM MODE - STOPPING ALGORITHM!")
                            self.stop()
                            return
                        
                        # Jeśli nie tryb alarmowy, ale błąd - pomiń tę iterację
                        self.error_logger.warning("Skipping iteration due to API failure")
                        continue
                    
                    # 2. Ładujemy dane tylko z API (nie z lokalnych plików!)
                    if os.path.exists(self.live_data_path):
                        self.load_live_data()
                    else:
                        self.error_logger.error("No live data available after API fetch")
                        continue
                else:
                    # Tryb bez API - użyj danych początkowych (tylko do testów)
                    self.load_initial_data()

                # 3. Wykonujemy algorytm
                result = self.run_single_iteration()
                
                # 4. Zapisujemy wyniki do plików wewnętrznych
                #self.save_live_data()
                self.save_contract_data()
                
                # 5. Wysyłamy tylko zmienione urządzenia do API
                if self.use_api:
                    # 5a. Sprawdź czy są jakiekolwiek zmiany
                    if self.has_device_changes():
                        # Przygotuj dane TYLKO dla zmienionych urządzeń
                        api_changed_data = self.prepare_changed_devices_for_api()
                        api_contract_data = self.prepare_contract_data_for_api()
                        
                        # 5b. Zapisz TYLKO zmienione urządzenia do output_data
                        os.makedirs(os.path.dirname(self.output_data_path), exist_ok=True)
                        with open(self.output_data_path, "w") as f:
                            json.dump(api_changed_data, f, indent=4)
                        
                        # Log podsumowania zmian
                        self.log_changed_devices_summary()
                        self.info_logger.info(f"Changed devices data saved to {self.output_data_path}")
                        
                        # 5c. Wyślij z retry logic
                        success = self.api_manager.send_updated_data_with_retry(
                            api_changed_data,  # Tylko zmienione urządzenia!
                            api_contract_data
                        )
                        
                        if not success:
                            self.error_logger.error("Failed to send data to API after all retry attempts")
                        else:
                            self.info_logger.info("Changed devices data sent to API successfully")
                    else:
                        self.info_logger.info("No device changes detected - skipping API POST operation")
                
                # 6. Aktualizujemy profil mocy
                self.update_power_profile(datetime.now())
                
                # 7. Loguj czas całej iteracji
                iteration_elapsed_time = time.time() - iteration_start_time
                self.info_logger.info(f"Complete iteration finished in {iteration_elapsed_time:.2f} seconds")

                # 8. Oczekiwanie na następną iterację
                wait_time = (
                    self.auto_interval
                    if self.operation_mode == OperationMode.AUTOMATIC
                    else self.semi_auto_interval
                )
                self.info_logger.important(f"Waiting {wait_time} seconds for next iteration")
                if self.stop_event.wait(wait_time):
                    break
                    
            except Exception as e:
                self.handle_runtime_error(e)
                break

        self.info_logger.important("Energy management stopped")

    def run_single_iteration(self):
        self.info_logger.highlight(
            f"Starting a new iteration in {self.operation_mode.value} mode"
        )
        start_time = time.time()

        self.info_logger.section("Starting device update based on meter readings")
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

        # self.info_logger.info(
        # f"BESS charge level before actions: {self.microgrid.bess.get_charge_level():.2f} kWh"
        # )

        result = self.check_energy_conditions()

        approved_actions = []
        if result is not None:
            if "approved_actions" in result:
                approved_actions = result["approved_actions"]

        # Wykonaj zatwierdzone akcje tylko raz
        if approved_actions:
            self.execute_approved_actions(approved_actions)

        self.log_system_summary()
        #self.save_live_data()
        self.save_contract_data()
        self.update_power_profile(datetime.now())

        elapsed_time = time.time() - start_time
        self.info_logger.info(f"Iteration completed in {elapsed_time:.2f} seconds")
        # self.info_logger.info(
        # f"BESS charge level after actions: {self.microgrid.bess.get_charge_level():.2f} kWh"
        # )

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
        except FileNotFoundError:
            self.info_logger.warning(f"Pending actions file not found. Creating empty file at {self.pending_actions_path}")
            # Upewnij się, że katalog istnieje
            os.makedirs(os.path.dirname(self.pending_actions_path), exist_ok=True)
            with open(self.pending_actions_path, "w") as file:
                json.dump([], file)
            return []
        except json.JSONDecodeError:
            self.error_logger.error(f"Error decoding pending actions file. File may be corrupted.")
            return []
        except Exception as e:
            self.error_logger.error(f"Unexpected error reading pending actions file: {str(e)}")
            return []

    def save_pending_actions(self, actions):
        try:
            # Upewnij się, że katalog istnieje
            os.makedirs(os.path.dirname(self.pending_actions_path), exist_ok=True)
            
            with open(self.pending_actions_path, "w") as f:
                json.dump(actions, f, indent=2)
            
            self.info_logger.info(f"Saved {len(actions)} pending actions")
            for action in actions:
                self.info_logger.info(f"Pending action: {json.dumps(action, indent=2)}")

            # Weryfikacja zapisu
            self.verify_file_content(self.pending_actions_path, "pending actions")
        except Exception as e:
            self.error_logger.error(f"Error saving pending actions: {str(e)}")

    def load_operator_decision(self):
        try:
            with open(self.operator_decisions_path, "r") as file:
                decisions = json.load(file)
                return decisions[0] if decisions else None
        except FileNotFoundError:
            self.info_logger.warning(f"Operator decisions file not found at {self.operator_decisions_path}")
            return None
        except json.JSONDecodeError:
            self.error_logger.error(f"Error decoding operator decisions file. File may be corrupted.")
            return None
        except Exception as e:
            self.error_logger.error(f"Unexpected error reading operator decisions: {str(e)}")
            return None

    def save_operator_decisions(self, decisions):
        try:
            # Upewnij się, że katalog istnieje
            os.makedirs(os.path.dirname(self.operator_decisions_path), exist_ok=True)
            
            with open(self.operator_decisions_path, "w") as f:
                json.dump(decisions, f, indent=2)
            
            self.info_logger.info(f"Saved {len(decisions)} operator decisions")
            for decision in decisions:
                self.info_logger.info(f"Operator decision: {json.dumps(decision, indent=2)}")

            # Weryfikacja zapisu
            self.verify_file_content(self.operator_decisions_path, "operator decisions")
        except Exception as e:
            self.error_logger.error(f"Error saving operator decisions: {str(e)}")

    def verify_file_content(self, file_path, file_description):
        try:
            with open(file_path, "r") as f:
                content = json.load(f)
            self.info_logger.info(
                f"Successfully verified {file_description} file. Content: {json.dumps(content, indent=2)}"
            )
        except FileNotFoundError:
            self.error_logger.error(f"File not found during verification: {file_path}")
        except json.JSONDecodeError:
            self.error_logger.error(f"Invalid JSON format in {file_description} file")
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
        device_type = type(device).__name__
        self.info_logger.info(
            f"[DEBUG] Performing action: {device_name} ({device_type}) - {action}"
        )

        try:
            if isinstance(device, EnergySource):
                result = self.perform_energy_source_action(device, action)
            elif isinstance(device, EnergyPoint):
                result = self.perform_energy_point_action(device, action)
            elif isinstance(device, BESS):
                result = self.perform_bess_action(device, action)
            elif isinstance(device, OSD):
                result = self.perform_osd_action(device, action)
            else:
                result = {
                    "success": False,
                    "amount": 0,
                    "reason": f"Unknown device type: {device_type}",
                }
            
            # NOWE: Jeśli akcja się powiodła, zapisz zmiany do śledzenia
            if result.get("success", False):
                device_change = {
                    "device": device,
                    "action": action,
                    "new_value": result.get("amount", 0),
                    "device_type": self.get_device_type(device)  # Używaj tej funkcji zamiast type().__name__
                }
                self.changed_devices.append(device_change)
                self.info_logger.info(f"✅ DEVICE CHANGED: {device_name} ({self.get_device_type(device)}) - {action}")
            
            return result
            
        except Exception as e:
            self.error_logger.exception(f"[DEBUG] Error in perform_action: {str(e)}")
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
            # Upewnij się, że katalog istnieje
            os.makedirs(os.path.dirname(self.operator_actions_path), exist_ok=True)
            self.save_operator_actions(actions)
            return actions
        except json.JSONDecodeError:
            self.error_logger.error(
                f"Error decoding operator_actions.json. File may be corrupted."
            )
            return {"pending_actions": [], "completed_actions": []}
        except Exception as e:
            self.error_logger.error(f"Unexpected error reading operator actions: {str(e)}")
            return {"pending_actions": [], "completed_actions": []}

    def save_operator_actions(self, actions):
        try:
            # Upewnij się, że katalog istnieje
            os.makedirs(os.path.dirname(self.operator_actions_path), exist_ok=True)
            
            with open(self.operator_actions_path, "w") as file:
                json.dump(actions, file, indent=2)
            
            self.info_logger.info(f"Saved operator actions: {len(actions['pending_actions'])} pending, {len(actions['completed_actions'])} completed")
        except Exception as e:
            self.error_logger.error(f"Error saving operator actions: {str(e)}")

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

            self.info_logger.info(
                f"checkTotal generated power: {total_generated_power} kW"
            )
            self.info_logger.info(f"checkTotal demand power: {total_demand_power} kW")

            result = None
            if total_generated_power > total_demand_power:
                power_surplus = total_generated_power - total_demand_power
                self.info_logger.section(
                    f"Power surplus detected: {power_surplus} kW - starting surplus management"
                )
                result = self.manage_surplus(power_surplus)
            elif total_generated_power < total_demand_power:
                power_deficit = total_demand_power - total_generated_power
                self.info_logger.section(
                    f"Power deficit detected: {power_deficit} kW - starting deficit management"
                )
                result = self.manage_deficit(power_deficit)
            else:
                self.info_logger.section(
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

        self.info_logger.important(
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

        self.info_logger.important(
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

        # Dodajemy sekcję dla podsumowania statusu systemu
        self.info_logger.section("System Status Summary")

        # Logujemy główne informacje
        self.info_logger.important(
            f"Total generated power: {total_generated_power:.2f} kW"
        )
        self.info_logger.important(f"Total demand: {total_demand_power:.2f} kW")
        self.info_logger.info(
            f"Number of active generating devices: {len(active_devices)}"
        )
        self.info_logger.info(
            f"Number of inactive generating devices: {len(inactive_devices)}"
        )

        if active_devices:
            self.info_logger.section("Active Generating Devices")
            for device in active_devices:
                self.info_logger.info(
                    f"  - {device.name}: {device.get_actual_output():.2f} kW / {device.get_max_output():.2f} kW"
                )

        if inactive_devices:
            self.info_logger.section("Inactive Generating Devices")
            for device in inactive_devices:
                self.info_logger.info(
                    f"  - {device.name}: max output {device.get_max_output():.2f} kW"
                )

        if self.microgrid.bess:
            bess = self.microgrid.bess
            self.info_logger.section("BESS Status")
            self.info_logger.info(
                f"BESS charge level: {bess.get_charge_level():.2f} kWh / {bess.get_capacity():.2f} kWh"
            )

        self.info_logger.section("Energy Trading Status")
        self.info_logger.info(
            f"Energy purchase: {'Available' if self.osd.can_buy_energy() else 'Not available'} "
            f"(Limit: {self.osd.get_purchase_limit():.2f} kWh, Current: {self.osd.get_bought_power():.2f} kWh)"
        )
        self.info_logger.info(
            f"Energy sale: {'Available' if self.osd.can_sell_energy() else 'Not available'} "
            f"(Limit: {self.osd.get_sale_limit():.2f} kWh, Current: {self.osd.get_sold_power():.2f} kWh)"
        )

        # Wywołujemy log_consumer_summary na końcu
        self.log_consumer_summary()

    def load_initial_data(self):
        self.info_logger.info("Starting to load initial data from files")
        self.microgrid.load_data_from_json(self.initial_data_path)
        self.consumergrid.load_data_from_json(self.initial_data_path)
        self.osd = OSD.load_data_from_json(
            self.initial_contract_path
        )  # ewentualnie do wywalenia, do przemyślenia
        if self.osd is None:
            raise ValueError("Failed to load OSD data from initial contract file.")
        self.surplus_manager.osd = self.osd
        self.deficit_manager.osd = self.osd
        self.info_logger.info("Finished loading initial data")

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

    def save_contract_data(self):
        """Generuje i zapisuje aktualne dane kontraktowe do osobnego pliku JSON."""
        try:
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

            # Upewnij się, że katalogi istnieją
            os.makedirs(os.path.dirname(self.output_contract_path), exist_ok=True)

            # Zapisujemy dane do pliku wyjściowego
            with open(self.output_contract_path, "w") as f:
                json.dump(contract_data, f, indent=4)

            self.info_logger.info(f"Live contract data saved to {self.output_contract_path}")
        except Exception as e:
            self.error_logger.error(f"Error saving contract data: {str(e)}")

    def update_power_profile(self, current_time):
        consumption = self.consumergrid.total_power_consumed()
        generation = self.microgrid.total_power_generated()
        buy_price = self.osd.get_current_buy_price()
        sell_price = self.osd.get_current_sell_price()

        try:
            self.power_profile_manager.update(
                current_time, consumption, generation, buy_price, sell_price
            )
            self.info_logger.info("Updated power profile")
        except Exception as e:
            self.error_logger.error(f"Error updating power profile: {str(e)}")

    def get_device_by_id_and_type(self, device_id, device_type):
        self.info_logger.info(
            f"[DEBUG] Entering get_device_by_id_and_type: ID={device_id}, type={device_type}"
        )

        if device_type == "OSD":
            self.info_logger.info("[DEBUG] Returning OSD device")
            return self.osd
        if device_type == "BESS":
            self.info_logger.info("[DEBUG] Checking BESS device")
            if self.microgrid.bess and str(self.microgrid.bess.id) == str(device_id):
                self.info_logger.info(
                    f"[DEBUG] BESS device found: ID={self.microgrid.bess.id}"
                )
                return self.microgrid.bess
            else:
                self.info_logger.info(
                    f"[DEBUG] BESS device not found or ID mismatch. BESS ID: {self.microgrid.bess.id if self.microgrid.bess else 'None'}"
                )

        device_lists = {
            "PV": self.microgrid.pv_panels,
            "WindTurbine": self.microgrid.wind_turbines,
            "FuelTurbine": self.microgrid.fuel_turbines,
            "FuelCell": self.microgrid.fuel_cells,
            "AdjustableDevice": self.consumergrid.adjustable_devices,
            "NonAdjustableDevice": self.consumergrid.non_adjustable_devices,
        }

        if device_type in device_lists:
            self.info_logger.info(f"[DEBUG] Searching in {device_type} list")
            for device in device_lists[device_type]:
                if str(device.id) == str(device_id):
                    self.info_logger.info(f"[DEBUG] Device found: {device.name}")
                    return device
            self.info_logger.info(
                f"[DEBUG] No device found with ID {device_id} in {device_type} list"
            )
        else:
            self.info_logger.info(f"[DEBUG] Unknown device type: {device_type}")

        self.error_logger.error(
            f"[DEBUG] Device not found: ID {device_id}, type {device_type}"
        )
        return None

    def execute_approved_actions(self, approved_actions):
        self.info_logger.info("Executing approved actions:")
        for action in approved_actions:
            self.info_logger.info(f"[DEBUG] Processing action: {action}")
            if action.get("executed", False):
                self.info_logger.info(
                    f"[DEBUG] Action already executed: {action['action']} for {action['device_name']}"
                )
                continue

            device = self.get_device_by_id_and_type(
                action["device_id"], action["device_type"]
            )
            if device:
                device_name = self.get_device_name(device)
                device_type = type(device).__name__
                self.info_logger.info(
                    f"[DEBUG] Device found: {device_name}, type: {device_type}"
                )

                self.log_device_state_before_action(device)

                result = self.perform_action(device, action["action"])

                if result["success"]:
                    self.log_device_state_after_action(
                        device, action["action"], result["amount"]
                    )
                else:
                    self.error_logger.error(
                        f"[DEBUG] Failed to execute action {action['action']} for {device_name}: {result.get('reason', 'Unknown reason')}"
                    )
            else:
                self.error_logger.error(
                    f"[DEBUG] Device not found for action: {action}"
                )

        self.log_system_summary()

    def get_device_by_id_and_type(self, device_id, device_type):
        self.info_logger.info(
            f"[DEBUG] Entering get_device_by_id_and_type: ID={device_id}, type={device_type}"
        )

        if device_type == "OSD":
            self.info_logger.info("[DEBUG] Returning OSD device")
            return self.osd
        if device_type == "BESS":
            self.info_logger.info("[DEBUG] Checking BESS device")
            return self.microgrid.bess if self.microgrid.bess else None

        device_lists = {
            "PV": self.microgrid.pv_panels,
            "PVPanel": self.microgrid.pv_panels,
            "WindTurbine": self.microgrid.wind_turbines,
            "FuelTurbine": self.microgrid.fuel_turbines,
            "FuelCell": self.microgrid.fuel_cells,
            "AdjustableDevice": self.consumergrid.adjustable_devices,
            "NonAdjustableDevice": self.consumergrid.non_adjustable_devices,
        }

        self.info_logger.info(
            f"[DEBUG] Available device types: {list(device_lists.keys())}"
        )
        self.info_logger.info(f"[DEBUG] Searching for device type: {device_type}")

        if device_type in device_lists:
            self.info_logger.info(
                f"[DEBUG] Device type {device_type} found in device_lists"
            )
            device_list = device_lists[device_type]
            self.info_logger.info(
                f"[DEBUG] Searching in {device_type} list. List length: {len(device_list)}"
            )
            for device in device_list:
                self.info_logger.info(
                    f"[DEBUG] Checking device: ID={device.id}, Name={device.name}, Type={type(device).__name__}"
                )
                self.info_logger.info(
                    f"[DEBUG] Comparing: '{str(device.id)}' == '{str(device_id)}' (types: {type(device.id)} and {type(device_id)})"
                )
                if str(device.id) == str(device_id):
                    self.info_logger.info(
                        f"[DEBUG] Found matching device: {device.name}"
                    )
                    return device
            self.info_logger.info(
                f"[DEBUG] No device found with ID {device_id} in {device_type} list"
            )
        else:
            self.error_logger.error(f"[DEBUG] Unknown device type: {device_type}")

        self.error_logger.error(
            f"[DEBUG] Device not found: ID {device_id}, type {device_type}"
        )
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

    def perform_energy_source_action(self, device, action):
        self.info_logger.info(f"Performing action: {action} on device: {device.name}")
        if action.startswith("set_output:"):
            _, new_output = action.split(":")
            new_output = float(new_output)
            current_output = device.get_actual_output()
            if device.set_output(new_output):
                actual_reduction = current_output - new_output
                self.info_logger.info(
                    f"Set output for {device.name} from {current_output} kW to {new_output} kW"
                )
                return {"success": True, "amount": actual_reduction}
            else:
                return {
                    "success": False,
                    "amount": 0,
                    "reason": f"Failed to set output for {device.name}",
                }
        elif action == "deactivate":
            current_output = device.get_actual_output()  # Dodajemy tę linię
            if device.deactivate():
                saved_power = current_output
                self.info_logger.info(
                    f"Deactivated {device.name}, saved {saved_power} kW"
                )
                return {"success": True, "amount": saved_power}
            else:
                return {
                    "success": False,
                    "amount": 0,
                    "reason": f"Failed to deactivate {device.name}",
                }
        elif action.startswith("activate_and_set:"):
            _, new_output = action.split(":")
            new_output = float(new_output)
            initial_output = device.get_actual_output()  # Dodajemy tę linię
            if device.activate():
                if device.set_output(new_output):
                    actual_increase = new_output - initial_output
                    self.info_logger.info(
                        f"Activated {device.name} and set output to {new_output} kW"
                    )
                    return {"success": True, "amount": actual_increase}
                else:
                    device.deactivate()  # Cofnij aktywację, jeśli nie udało się ustawić mocy
                    return {
                        "success": False,
                        "amount": 0,
                        "reason": f"Failed to set output for {device.name} after activation",
                    }
            else:
                return {
                    "success": False,
                    "amount": 0,
                    "reason": f"Failed to activate {device.name}",
                }
        else:
            return {
                "success": False,
                "amount": 0,
                "reason": f"Unknown action for EnergySource: {action}",
            }

    def perform_energy_point_action(self, device, action):
        if action == "deactivate":
            if device.deactivate():
                return {"success": True, "amount": device.get_current_power()}
            else:
                return {
                    "success": False,
                    "amount": 0,
                    "reason": f"Failed to deactivate {device.name}",
                }
        elif action.startswith("reduce:"):
            if isinstance(device, AdjustableDevice):
                _, amount = action.split(":")
                amount = float(amount)
                actual_reduction = device.decrease_power(amount)
                return {"success": True, "amount": actual_reduction}
            else:
                return {
                    "success": False,
                    "amount": 0,
                    "reason": f"Cannot reduce power for non-adjustable device {device.name}",
                }
        elif action == "activate":
            device.activate()
            return {"success": True, "amount": device.get_current_power()}
        else:
            return {
                "success": False,
                "amount": 0,
                "reason": f"Unknown action for EnergyPoint: {action}",
            }

    def perform_bess_action(self, device, action):
        if action.startswith("charge:"):
            _, amount = action.split(":")
            amount = float(amount)
            charged_amount, charged_percent = device.charge(amount)
            if charged_amount > 0:
                return {
                    "success": True,
                    "amount": charged_amount,
                    "percent": charged_percent,
                }
            else:
                return {
                    "success": False,
                    "amount": 0,
                    "percent": 0,
                    "reason": f"Failed to charge BESS {device.name}",
                }
        elif action.startswith("discharge:"):
            _, amount = action.split(":")
            amount = float(amount)
            discharged_amount, discharged_percent = device.discharge(amount)
            if discharged_amount > 0:
                return {
                    "success": True,
                    "amount": discharged_amount,
                    "percent": discharged_percent,
                }
            else:
                return {
                    "success": False,
                    "amount": 0,
                    "percent": 0,
                    "reason": f"Failed to discharge BESS {device.name}",
                }
        else:
            return {
                "success": False,
                "amount": 0,
                "percent": 0,
                "reason": f"Unknown action for BESS: {action}",
            }

    def perform_osd_action(self, device, action):
        if action.startswith("buy:"):
            _, amount = action.split(":")
            amount = float(amount)
            if device.buy_power(amount):
                return {"success": True, "amount": amount}
            else:
                return {
                    "success": False,
                    "amount": 0,
                    "reason": f"Failed to buy power from OSD",
                }
        elif action.startswith("sell:"):
            _, amount = action.split(":")
            amount = float(amount)
            if device.sell_power(amount):
                return {"success": True, "amount": amount}
            else:
                return {
                    "success": False,
                    "amount": 0,
                    "reason": f"Failed to sell power to OSD",
                }
        else:
            return {
                "success": False,
                "amount": 0,
                "reason": f"Unknown action for OSD: {action}",
            }

    def log_device_state_before_action(self, device):
        if isinstance(device, EnergySource):
            self.info_logger.info(
                f"Before action: {device.name} output: {device.get_actual_output()} kW"
            )
        elif isinstance(device, EnergyPoint):
            self.info_logger.info(
                f"Before action: {device.name} power: {device.get_current_power()} kW"
            )
        elif isinstance(device, BESS):
            self.info_logger.info(
                f"Before action: {device.name} charge level: {device.get_charge_level()} kWh"
            )
        elif isinstance(device, OSD):
            self.info_logger.info(
                f"Before action: OSD current sold power: {device.get_sold_power()} kW"
            )

    def log_device_state_after_action(self, device, action, amount):
        if isinstance(device, EnergySource):
            self.info_logger.info(
                f"After action: {device.name} output: {device.get_actual_output()} kW"
            )
        elif isinstance(device, EnergyPoint):
            self.info_logger.info(
                f"After action: {device.name} power: {device.get_current_power()} kW"
            )
        elif isinstance(device, BESS):
            self.info_logger.info(
                f"After action: {device.name} charge level: {device.get_charge_level()} kWh"
            )
        elif isinstance(device, OSD):
            self.info_logger.info(
                f"After action: OSD new sold power: {device.get_sold_power()} kW"
            )

        device_name = self.get_device_name(device)
        self.info_logger.info(
            f"Executed {action} for {device_name}: Success. Amount: {amount} kW"
        )

    def get_device_name(self, device):
        if isinstance(device, OSD):
            return "OSD"
        return device.name if hasattr(device, "name") else str(device)

    def log_consumer_summary(self):
        total_consumed_power = self.consumergrid.total_power_consumed()
        active_devices = self.consumergrid.get_active_devices()
        all_devices = self.consumergrid.get_all_devices()
        inactive_devices = [
            device for device in all_devices if device not in active_devices
        ]

        adjustable_devices = [
            device for device in active_devices if isinstance(device, AdjustableDevice)
        ]
        non_adjustable_devices = [
            device
            for device in active_devices
            if not isinstance(device, AdjustableDevice)
        ]

        # Główna sekcja podsumowania konsumentów energii
        self.info_logger.section("Energy Consumer Grid Summary")

        # Kluczowe informacje
        self.info_logger.important(
            f"Total consumed power: {total_consumed_power:.2f} kW"
        )
        self.info_logger.info(f"Total number of devices: {len(all_devices)}")
        self.info_logger.info(f"Number of active devices: {len(active_devices)}")
        self.info_logger.info(f"Number of inactive devices: {len(inactive_devices)}")
        self.info_logger.info(
            f"Number of active adjustable devices: {len(adjustable_devices)}"
        )
        self.info_logger.info(
            f"Number of active non-adjustable devices: {len(non_adjustable_devices)}"
        )

        # Sekcja aktywnych urządzeń regulowanych
        if adjustable_devices:
            self.info_logger.section("Active Adjustable Devices")
            for device in adjustable_devices:
                self.info_logger.info(
                    f"  - {device.name}: Current: {device.get_current_power():.2f} kW / Max: {device.power:.2f} kW"
                )

        # Sekcja aktywnych urządzeń nieregulowanych
        if non_adjustable_devices:
            self.info_logger.section("Active Non-adjustable Devices")
            for device in non_adjustable_devices:
                self.info_logger.info(
                    f"  - {device.name}: {device.get_current_power():.2f} kW"
                )

        # Sekcja nieaktywnych urządzeń
        if inactive_devices:
            self.info_logger.section("Inactive Devices")
            for device in inactive_devices:
                device_type = (
                    "Adjustable"
                    if isinstance(device, AdjustableDevice)
                    else "Non-adjustable"
                )
                self.info_logger.info(f"  - {device.name} ({device_type})")

    # def prepare_system_data_for_api(self):
    #     """
    #     Przygotowuje dane systemu w formacie API do wysłania.
        
    #     Returns:
    #         dict: Słownik zawierający dane systemu w formacie API.
    #     """
    #     api_data = {
    #         "pv_panels": [],
    #         "wind_turbines": [],
    #         "fuel_turbines": [],
    #         "fuel_cells": [],
    #         "bess": [],
    #         "non_adjustable_devices": [],
    #         "adjustable_devices": []
    #     }
        
    #     # Konwersja źródeł energii
    #     for category, devices in [
    #         ("pv_panels", self.microgrid.pv_panels),
    #         ("wind_turbines", self.microgrid.wind_turbines),
    #         ("fuel_turbines", self.microgrid.fuel_turbines),
    #         ("fuel_cells", self.microgrid.fuel_cells)
    #     ]:
    #         for device in devices:
    #             api_data[category].append({
    #                 "name": device.name,
    #                 "actual_output": device.get_actual_output(),
    #                 "switch_status": device.switch_status
    #             })
        
    #     # Konwersja BESS
    #     if self.microgrid.bess:
    #         api_data["bess"].append({
    #             "name": self.microgrid.bess.name,
    #             "actual_output": 0,  # BESS nie ma actual_output w API
    #             "switch_status": self.microgrid.bess.switch_status
    #         })
        
    #     # Konwersja urządzeń konsumpcyjnych
    #     for device in self.consumergrid.non_adjustable_devices:
    #         api_data["non_adjustable_devices"].append({
    #             "name": device.name,
    #             "actual_output": device.get_current_power(),
    #             "switch_status": device.switch_status
    #         })
        
    #     for device in self.consumergrid.adjustable_devices:
    #         api_data["adjustable_devices"].append({
    #             "name": device.name,
    #             "actual_output": device.get_current_power(),
    #             "switch_status": device.switch_status
    #         })
        
    #     return api_data

    def prepare_contract_data_for_api(self):
        """
        Przygotowuje dane kontraktu w formacie API do wysłania.
        
        Returns:
            dict: Słownik zawierający dane kontraktu w formacie API.
        """
        return {
            "contracted_type": self.osd.CONTRACTED_TYPE,
            "contracted_duration": self.osd.CONTRACTED_DURATION,
            "contracted_margin": self.osd.CONTRACTED_MARGIN,
            "contracted_export_possibility": self.osd.CONTRACTED_EXPORT_POSSIBILITY,
            "contracted_sale_limit": self.osd.CONTRACTED_SALE_LIMIT,
            "contracted_purchase_limit": self.osd.CONTRACTED_PURCHASE_LIMIT,
            "sold_power": self.osd.get_sold_power(),
            "bought_power": self.osd.get_bought_power(),
            "current_tariff_buy": self.osd.get_current_buy_price(),
            "current_tariff_sell": self.osd.get_current_sell_price()
        }
    
    def prepare_changed_devices_for_api(self):
        """Przygotowuje dane API tylko dla urządzeń zmienionych przez algorytm."""
        api_data = {}
        
        for change in self.changed_devices:
            device = change["device"]
            device_type = change["device_type"]

            # DODAJ TO - obsługa OSD:
            if device_type == "OSD":
                # OSD nie jest wysyłane jako urządzenie, tylko jako dane kontraktu
                # Więc pomijamy je tutaj - będzie obsłużone przez prepare_contract_data_for_api()
                continue
            
            device_api_data = {
                "name": device.name,
                "switch_status": device.switch_status if hasattr(device, 'switch_status') else True
            }
            
            if device_type == "BESS":
                device_api_data["charge_level"] = device.get_charge_level()
                if "bess" not in api_data:
                    api_data["bess"] = []
                api_data["bess"].append(device_api_data)
                
            elif device_type in ["PV", "WindTurbine", "FuelTurbine", "FuelCell"]:
                device_api_data["actual_output"] = device.get_actual_output()
                category_map = {
                    "PV": "pv_panels",
                    "WindTurbine": "wind_turbines", 
                    "FuelTurbine": "fuel_turbines",
                    "FuelCell": "fuel_cells"
                }
                category = category_map.get(device_type, "pv_panels")
                if category not in api_data:
                    api_data[category] = []
                api_data[category].append(device_api_data)
                
            elif device_type in ["AdjustableDevice", "NonAdjustableDevice"]:
                device_api_data["actual_output"] = device.get_current_power()
                category = "adjustable_devices" if device_type == "AdjustableDevice" else "non_adjustable_devices"
                if category not in api_data:
                    api_data[category] = []
                api_data[category].append(device_api_data)
        
        return api_data

    def has_device_changes(self):
        """Sprawdza czy algorytm wykonał jakiekolwiek zmiany na urządzeniach."""
        return len(self.changed_devices) > 0

    def reset_changed_devices(self):
        """Resetuje listę zmienionych urządzeń na początku każdej iteracji."""
        self.changed_devices = []
        
    def log_changed_devices_summary(self):
        """Loguje podsumowanie zmienionych urządzeń."""
        if not self.changed_devices:
            self.info_logger.info("No devices were changed by the algorithm in this iteration")
            return
        
        self.info_logger.section("Algorithm Changes Summary")
        for change in self.changed_devices:
            device = change["device"]
            action = change["action"]
            device_type = change["device_type"]
            
            if device_type == "BESS":
                self.info_logger.info(f"  - BESS '{device.name}': {action} → charge_level: {device.get_charge_level():.2f} kWh")
            elif hasattr(device, 'get_actual_output'):
                self.info_logger.info(f"  - {device_type} '{device.name}': {action} → actual_output: {device.get_actual_output():.2f} kW")
            elif hasattr(device, 'get_current_power'):
                self.info_logger.info(f"  - {device_type} '{device.name}': {action} → power: {device.get_current_power():.2f} kW")
