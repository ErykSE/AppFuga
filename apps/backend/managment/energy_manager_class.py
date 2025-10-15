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
from apps.backend.managment.heartbeat_tag_sender import HeartbeatTagSender

from apps.backend.managment.bess_capability_checker import BESSCapabilityChecker
from apps.backend.managment.iteration_scheduler import IterationScheduler

from apps.backend.managment.energy_balance import EnergyBalance

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
        self.auto_interval = 300  # 15 sekund dla trybu automatycznego
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
        #self.info_logger.info(f"Base path: {self.base_path}")
        #self.info_logger.info(f"Initial data path: {self.initial_data_path}")
        #self.info_logger.info(f"Initial contract path: {self.initial_contract_path}")

        self.use_api = use_api
    
        # Inicjalizacja ApiManager
        if self.use_api:
            self.api_manager = ApiManager(
                api_base_url=api_base_url,
                info_logger=info_logger,
                error_logger=error_logger,
                verify_ssl=False
            )

        # Heartbeat tag sender
        self.heartbeat_sender = None  # ← Na początku nie ma heartbeat sendera
        if self.use_api:  # ← Jeśli używamy API
            self.heartbeat_sender = HeartbeatTagSender(  # ← Stwórz nowy obiekt
                api_base_url=api_base_url,              # ← Adres API
                info_logger=info_logger,                # ← Logger do info
                error_logger=error_logger,              # ← Logger do błędów
                verify_ssl=False                        # ← Bez weryfikacji SSL
            )


        #self.info_logger.info(f"Using API: {self.use_api}")

        self.changed_devices = []

        # === NARZĘDZIA POMOCNICZE ===
    
        # BESS Capability Checker (lazy initialization)
        self.bess_checker = None  # Zostanie utworzony po załadowaniu danych
        
        # Iteration Scheduler
        self.iteration_scheduler = IterationScheduler(
            normal_interval_seconds=self.auto_interval,
            info_logger=info_logger,
            error_logger=error_logger
        )

        # ===================================================================
        # ETAP 2: Tracking poprzednich stanów i ograniczeń
        # ===================================================================
        self.previous_device_states = {}  # Śledzenie poprzednich stanów urządzeń
        self.artificial_limitations = []  # Lista sztucznie nałożonych ograniczeń
        self.operation_history = []  # Historia operacji (dla analizy)

        #self.info_logger.info(f"✅ IterationScheduler initialized")

        # === SUMMARY ===
        #self.info_logger.info("=" * 70)
        #self.info_logger.info("ENERGY MANAGER INITIALIZATION COMPLETE")
        #self.info_logger.info(f"  Operation mode: {self.operation_mode.value if hasattr(self.operation_mode, 'value') else self.operation_mode}")
        #self.info_logger.info(f"  Auto interval: {self.auto_interval}s ({self.auto_interval/60:.1f} min)")
        #self.info_logger.info(f"  BESS available: {self.microgrid.bess is not None}")
        #self.info_logger.info(f"  BESSCapabilityChecker: {self.bess_checker is not None}")
        #self.info_logger.info(f"  IterationScheduler: {self.iteration_scheduler is not None}")
        #self.info_logger.info(f"  Decision mode: {getattr(self.osd, 'decision_mode', 'AUTO')}")
        #self.info_logger.info(f"  Use API: {self.use_api}")
        #self.info_logger.info("=" * 70)





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

        if self.heartbeat_sender:  # ← Jeśli heartbeat sender istnieje
            self.heartbeat_sender.start()  # ← URUCHOM go (osobny wątek!)

        Thread(target=self.run_energy_management).start()
        self.info_logger.important("Energy management started")

    def stop(self):
        """Zatrzymuje proces zarządzania energią."""
        self.running = False
        self.stop_event.set()

        if self.heartbeat_sender:  # ← Jeśli heartbeat sender istnieje
            self.heartbeat_sender.stop()  # ← ZATRZYMAJ go

        self.info_logger.important("Energy management stopping")

    def run_energy_management(self):
        """Uruchamia proces zarządzania energią w osobnym wątku."""
        while self.running and not self.stop_event.is_set():
            try:
                # Oznacz początek iteracji
                self.iteration_scheduler.mark_iteration_start()
                iteration_start_time = time.time()
                
                # Resetuj listę zmian na początku iteracji
                self.reset_changed_devices()
                
                self.info_logger.highlight("Starting new iteration")
                self.load_configuration()

                # Sprawdź czy są eventy do wykonania
                triggered_events = self.iteration_scheduler.check_for_triggered_events()
                if triggered_events:
                    self.handle_triggered_events(triggered_events)

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
                # Użyj schedulera aby dynamicznie dostosować czas
                wait_time = self.iteration_scheduler.get_next_wait_time()
                
                self.info_logger.important(f"Waiting {wait_time:.1f} seconds for next iteration")
                if self.stop_event.wait(wait_time):
                    break
                    
            except Exception as e:
                self.handle_runtime_error(e)
                break

        self.info_logger.important("Energy management stopped")

    def run_single_iteration(self):
        """
        Wykonuje jedną iterację zarządzania energią.
        """
        #self.info_logger.highlight("=" * 70)
        self.info_logger.highlight("NEW ITERATION START")
        #self.info_logger.highlight("=" * 70)
        start_time = time.time()

        # NOWE: Resetuj setpointy grid na początku każdej iteracji
        self.osd.reset_current_grid_values()

        # Resetuj listę zmienionych urządzeń
        self.reset_changed_devices()

        # Oblicz początkowy bilans energetyczny
        self.initial_energy_balance = self.microgrid.total_power_generated() - self.consumergrid.total_power_consumed()

        # Aktualizuj urządzenia na podstawie odczytów mierników
        updated_devices = self.microgrid.update_device_with_meter_data()
        if updated_devices:
            self.info_logger.info(
                f"📊 Updated {len(updated_devices)} devices based on meter readings"
            )
            for device in updated_devices:
                self.info_logger.info(
                    f"  • {device.name}: status={device.device_status}, output={device.actual_output} kW"
                )
        
        # ✅ ZMIANA: Zaloguj status TYLKO RAZ na początku (bez sekcji)
        self._log_initial_system_status()

        # Sprawdź warunki energetyczne i podejmij odpowiednie działania
        self.info_logger.info("DEBUG: About to call check_energy_conditions")
        self.info_logger.info("DEBUG: This is a test message to verify code execution")
        result = self.check_energy_conditions()
        self.info_logger.info("DEBUG: check_energy_conditions completed")

        # Wykonaj zatwierdzone akcje jeśli istnieją
        approved_actions = []
        if result is not None:
            if "approved_actions" in result:
                approved_actions = result["approved_actions"]

        # Wykonaj zatwierdzone akcje tylko raz
        if approved_actions:
            self.execute_approved_actions(approved_actions)

        # ✅ ZMIANA: Zaloguj status TYLKO RAZ na końcu (jeśli były zmiany)
        if self.has_device_changes():
            self._log_final_system_status()
        
        # Zapisz dane kontraktu
        self.save_contract_data()
        
        # Aktualizuj profil mocy
        self.update_power_profile(datetime.now())

        # Zaloguj operacje grid dla SCADA
        self.log_grid_operations_for_scada()

        # Oblicz czas wykonania iteracji
        elapsed_time = time.time() - start_time
        
        #self.info_logger.highlight("=" * 70)
        self.info_logger.highlight(f"ITERATION COMPLETE in {elapsed_time:.2f}s")
        #self.info_logger.highlight("=" * 70)

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
        device_name = self.get_device_name(device)  # ← MUSI używać bezpiecznej funkcji!
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
                self.info_logger.info(f"DEVICE CHANGED: {device_name} ({self.get_device_type(device)}) - {action}")
            
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

    # apps/backend/managment/energy_manager_class.py

    def check_energy_conditions(self):
        """
        Sprawdza warunki energetyczne i podejmuje odpowiednie działania.
        """
        self.info_logger.info("DEBUG: check_energy_conditions START")
        try:
            # ✅ WYCZYŚĆ LISTĘ ZMIAN NA POCZĄTKU
            self.changed_devices = []
            self.info_logger.info("DEBUG: changed_devices cleared")
            
            # ═══════════════════════════════════════════════════════
            # KROK 1: Oblicz początkowy bilans
            # ═══════════════════════════════════════════════════════
            self.info_logger.info("")
            self.info_logger.info("🔍" + "="*80)
            self.info_logger.info("🔍 ENERGY MANAGEMENT ITERATION START")
            self.info_logger.info("🔍" + "="*80)
            
            initial_balance = self.calculate_energy_balance()
            
            # ✅ UPROSZCZONE: Stan początkowy
            self.info_logger.info("DEBUG: Calling _log_initial_state")
            self.info_logger.info("DEBUG: About to call _log_initial_state method")
            try:
                self._log_initial_state(initial_balance)
                self.info_logger.info("DEBUG: _log_initial_state completed successfully")
            except Exception as e:
                self.info_logger.error(f"DEBUG: Error in _log_initial_state: {e}")
            
            # ═══════════════════════════════════════════════════════
            # KROK 2: Sprawdź czy bilans OK
            # ═══════════════════════════════════════════════════════
            if initial_balance.is_balanced(threshold=1.0):
                # ✅ ZMIANA: Wywołaj summary PRZED return!
                self._log_operator_summary(
                    initial_balance=initial_balance,
                    final_balance=initial_balance,  # Bez zmian
                    actions_taken=[],  # Pusta lista
                    decision_rationale="System balanced - no action required"
                )
                return None
            
            # ═══════════════════════════════════════════════════════
            # KROK 3: Neutralizuj konflikty
            # ═══════════════════════════════════════════════════════
            self.info_logger.info("")
            self.info_logger.info("🔧 NEUTRALIZING CONFLICTING OPERATIONS")
            self.info_logger.info("-" * 50)
            
            balance = self.neutralize_conflicting_operations(initial_balance)
            
            # ✅ UPROSZCZONE: Stan po neutralizacji (tylko jeśli były zmiany)
            if self.changed_devices:
                self._log_after_neutralization(balance)
            
            # ═══════════════════════════════════════════════════════
            # KROK 4: Sprawdź czy po neutralizacji bilans OK
            # ═══════════════════════════════════════════════════════
            if balance.is_balanced(threshold=1.0):
                # ✅ ZMIANA: Wywołaj summary PRZED return!
                self._log_operator_summary(
                    initial_balance=initial_balance,
                    final_balance=balance,
                    actions_taken=self.changed_devices,  # Neutralizacje
                    decision_rationale="Balance achieved after neutralization"
                )
                return None
            
            # ═══════════════════════════════════════════════════════
            # KROK 5: Przywróć ograniczenia (ETAP 2)
            # ═══════════════════════════════════════════════════════
            balance = self.restore_previous_limitations(balance)
            
            # ═══════════════════════════════════════════════════════
            # KROK 6: Sprawdź czy po przywróceniu bilans OK
            # ═══════════════════════════════════════════════════════
            if balance.is_balanced(threshold=1.0):
                # ✅ ZMIANA: Wywołaj summary PRZED return!
                self._log_operator_summary(
                    initial_balance=initial_balance,
                    final_balance=balance,
                    actions_taken=self.changed_devices,
                    decision_rationale="Balance achieved after restoring limitations"
                )
                return None
            
            # ═══════════════════════════════════════════════════════
            # KROK 7: Zarządzaj deficytem/nadwyżką
            # ═══════════════════════════════════════════════════════
            result = None
            decision_text = None
            
            if balance.has_surplus:
                self.info_logger.section(
                    f"⚡ Surplus REMAINING: {balance.surplus:.2f} kW → managing"
                )
                result = self.manage_surplus(balance.surplus)
                decision_text = f"Managed {balance.surplus:.2f} kW surplus"
                
            elif balance.has_deficit:
                self.info_logger.section(
                    f"📉 Deficit REMAINING: {balance.deficit:.2f} kW → managing"
                )
                result = self.manage_deficit(balance.deficit)
                decision_text = f"Managed {balance.deficit:.2f} kW deficit"
            
            # ═══════════════════════════════════════════════════════
            # KROK 8: Wywołaj summary NA KOŃCU (po wszystkich akcjach)
            # ═══════════════════════════════════════════════════════
            final_balance = self.calculate_energy_balance()
            
            # ✅ UPROSZCZONE: Stan końcowy (tylko jeśli były zmiany)
            if self.changed_devices:
                self._log_final_state(final_balance)
            
            self._log_operator_summary(
                initial_balance=initial_balance,
                final_balance=final_balance,
                actions_taken=self.changed_devices,
                decision_rationale=decision_text
            )
            
            return result
            
        except Exception as e:
            self.error_logger.error(f"Error checking energy conditions: {str(e)}")
            self.error_logger.exception("Full traceback:")
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

    '''
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

    '''

    def load_initial_data(self):
        #self.info_logger.info("Starting to load initial data from files")
        self.microgrid.load_data_from_json(self.initial_data_path)
        self.consumergrid.load_data_from_json(self.initial_data_path)
        self.osd = OSD.load_data_from_json(
            self.initial_contract_path
        )  # ewentualnie do wywalenia, do przemyślenia
        if self.osd is None:
            raise ValueError("Failed to load OSD data from initial contract file.")
        self.surplus_manager.osd = self.osd
        self.deficit_manager.osd = self.osd
        #self.info_logger.info("Finished loading initial data")
        self._ensure_bess_checker()

    # energy_manager.py - load_live_data

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
            self._ensure_bess_checker()  # ← DODAJ TĘ LINIĘ (jeśli jej nie ma)
            
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

        #self.log_system_summary()

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
        """
        Wykonuje akcję na źródle energii (PV, WindTurbine, FuelTurbine, FuelCell).
        
        Args:
            device: Obiekt źródła energii
            action: Akcja do wykonania
            
        Returns:
            dict: Wynik operacji
        """
        self.info_logger.info(f"Performing action: {action} on device: {device.name}")
        
        if action.startswith("set_output:"):
            _, new_output = action.split(":")
            new_output = float(new_output)
            current_output = device.get_actual_output()
            
            if device.set_output(new_output):
                # ✅ DODANE: Ustaw setpoint dla SCADA
                device.setpoint_output = new_output
                
                actual_reduction = current_output - new_output
                self.info_logger.info(
                    f"Set output for {device.name} from {current_output} kW to {new_output} kW. "
                    f"Setpoint: {device.setpoint_output} kW"
                )
                return {"success": True, "amount": actual_reduction}
            else:
                return {
                    "success": False,
                    "amount": 0,
                    "reason": f"Failed to set output for {device.name}",
                }
                
        elif action == "deactivate":
            current_output = device.get_actual_output()
            
            if device.deactivate():
                # ✅ DODANE: Ustaw setpoint na 0 (urządzenie wyłączone)
                device.setpoint_output = 0
                
                saved_power = current_output
                self.info_logger.info(
                    f"Deactivated {device.name}, saved {saved_power} kW. Setpoint: 0 kW"
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
            initial_output = device.get_actual_output()
            
            if device.activate():
                if device.set_output(new_output):
                    # ✅ DODANE: Ustaw setpoint dla SCADA
                    device.setpoint_output = new_output
                    
                    actual_increase = new_output - initial_output
                    self.info_logger.info(
                        f"Activated {device.name} and set output to {new_output} kW. "
                        f"Setpoint: {device.setpoint_output} kW"
                    )
                    return {"success": True, "amount": actual_increase}
                else:
                    device.deactivate()  # Cofnij aktywację
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
        """
        Wykonuje akcję na punkcie energetycznym (AdjustableDevice, NonAdjustableDevice).
        
        Args:
            device: Obiekt punktu energetycznego
            action: Akcja do wykonania
            
        Returns:
            dict: Wynik operacji
        """
        if action == "deactivate":
            current_power = device.get_current_power()
            
            if device.deactivate():
                # ✅ DODANE: Ustaw setpoint na 0
                device.setpoint_output = 0
                
                self.info_logger.info(f"Deactivated {device.name}. Setpoint: 0 kW")
                return {"success": True, "amount": current_power}
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
                
                # ✅ DODANE: Ustaw setpoint (nowa moc po redukcji)
                device.setpoint_output = device.get_current_power()
                
                self.info_logger.info(
                    f"Reduced {device.name} by {actual_reduction} kW. "
                    f"New power: {device.get_current_power()} kW, Setpoint: {device.setpoint_output} kW"
                )
                return {"success": True, "amount": actual_reduction}
            else:
                return {
                    "success": False,
                    "amount": 0,
                    "reason": f"Cannot reduce power for non-adjustable device {device.name}",
                }
                
        elif action == "activate":
            if device.activate():
                current_power = device.get_current_power()
                
                # ✅ DODANE: Ustaw setpoint (moc po aktywacji)
                device.setpoint_output = current_power
                
                self.info_logger.info(
                    f"Activated {device.name}. Power: {current_power} kW, Setpoint: {device.setpoint_output} kW"
                )
                return {"success": True, "amount": current_power}
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
        """
        Wykonuje akcję na OSD (zakup/sprzedaż energii).
        
        Args:
            device: Obiekt OSD
            action: Akcja do wykonania (buy:amount lub sell:amount)
        
        Returns:
            dict: Wynik operacji z sukcesem i ilością
        """
        if action.startswith("buy:"):
            _, amount_str = action.split(":")
            amount = float(amount_str)
            
            # buy_power już zwraca rzeczywistą ilość zakupioną
            actual_bought = device.buy_power(amount)
            
            if actual_bought > 0:
                self.info_logger.info(f"Successfully bought {actual_bought} kW from grid")
                self.info_logger.info(f"Grid import setpoint: {device.get_current_grid_import()} kW")
                return {"success": True, "amount": actual_bought}
            else:
                return {
                    "success": False,
                    "amount": 0,
                    "reason": f"Failed to buy power from grid - remaining capacity: {device.get_remaining_purchase_capacity()}"
                }
                
        elif action.startswith("sell:"):
            _, amount_str = action.split(":")
            amount = float(amount_str)
            
            # sell_power już zwraca rzeczywistą ilość sprzedaną
            actual_sold = device.sell_power(amount)
            
            if actual_sold > 0:
                self.info_logger.info(f"Successfully sold {actual_sold} kW to grid")
                self.info_logger.info(f"Grid export setpoint: {device.get_current_grid_export()} kW")
                return {"success": True, "amount": actual_sold}
            else:
                return {
                    "success": False,
                    "amount": 0,
                    "reason": f"Failed to sell power to grid - remaining capacity: {device.get_remaining_sale_capacity()}"
                }
        else:
            return {
                "success": False,
                "amount": 0,
                "reason": f"Unknown OSD action: {action}"
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
        """Zwraca nazwę urządzenia (bezpieczna dla OSD)."""
        if isinstance(device, OSD):
            return "OSD"
        return device.name if hasattr(device, "name") else str(device)

    
    '''
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
        '''

    def prepare_contract_data_for_api(self):
        """
        Przygotowuje dane kontraktu w formacie API C# (snake_case).
        
        Mapowanie pól:
        - sold_power, bought_power: skumulowana energia (kWh) od początku okresu
        - grid_export, grid_import: setpointy mocy (kW) dla bieżącej iteracji
        - setpoint_grid_export, setpoint_grid_import: duplikaty (wymagane przez API C#)
        
        Returns:
            dict: Dane kontraktu w formacie zgodnym z API C#
        """
        return {
            # === DANE KONTRAKTOWE (stałe) ===
            "contracted_type": self.osd.CONTRACTED_TYPE,
            "contracted_duration": self.osd.CONTRACTED_DURATION,
            "contracted_margin": self.osd.CONTRACTED_MARGIN,
            "contracted_export_possibility": self.osd.CONTRACTED_EXPORT_POSSIBILITY,
            "contracted_sale_limit": self.osd.CONTRACTED_SALE_LIMIT,
            "contracted_purchase_limit": self.osd.CONTRACTED_PURCHASE_LIMIT,
            
            # === CYKL ROZLICZENIOWY ===
            "contracted_billing_cycle": self.osd.contracted_billing_cycle,
            "contracted_billing_period_start": self.osd.contracted_billing_period_start,
            "contracted_billing_period_end": self.osd.contracted_billing_period_end,
            
            # === DANE SKUMULOWANE (kWh od początku okresu rozliczeniowego) ===
            "sold_power": self.osd.get_sold_power(),      # Całkowita sprzedana energia
            "bought_power": self.osd.get_bought_power(),  # Całkowita kupiona energia
            
            # === TARYFY (PLN/kWh) ===
            "current_tariff_buy": self.osd.get_current_buy_price(),
            "current_tariff_sell": self.osd.get_current_sell_price(),
            
            # === SETPOINTY MOCY dla SCADA (kW - BIEŻĄCA iteracja) ===
            # Uwaga: API wymaga duplikacji - grid_* to alias dla setpoint_grid_*
            "grid_export": self.osd.current_grid_export,         # kW do eksportu (setpoint)
            "grid_import": self.osd.current_grid_import,         # kW do importu (setpoint)
            "setpoint_grid_export": self.osd.current_grid_export,  # Duplikat dla kompatybilności
            "setpoint_grid_import": self.osd.current_grid_import,  # Duplikat dla kompatybilności
        }
    
    def prepare_changed_devices_for_api(self):
        """
        Przygotowuje dane API tylko dla urządzeń zmienionych przez algorytm.
        Używa setpoint_output zamiast actual_output dla SCADA.
        """
        api_data = {}
        
        for change in self.changed_devices:
            device = change["device"]
            device_type = change["device_type"]

            if device_type == "OSD":
                # OSD nie jest wysyłane jako urządzenie, tylko jako dane kontraktu
                continue
            
            device_api_data = {
                "name": device.name,
                "switch_status": device.switch_status if hasattr(device, 'switch_status') else True
            }
            
            if device_type == "BESS":
                # ✅ POPRAWKA: Używamy setpoint_output (ujemny = ładowanie, dodatni = rozładowanie)
                device_api_data["setpoint_output"] = device.setpoint_output
                device_api_data["charge_level"] = device.get_charge_level()
                
                if "bess" not in api_data:
                    api_data["bess"] = []
                api_data["bess"].append(device_api_data)
                
            elif device_type in ["PV", "WindTurbine", "FuelTurbine", "FuelCell"]:
                # ✅ POPRAWKA: Używamy setpoint_output zamiast actual_output
                device_api_data["setpoint_output"] = device.setpoint_output
                
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
                # ✅ POPRAWKA: Używamy setpoint_output zamiast actual_output
                device_api_data["setpoint_output"] = device.setpoint_output
                
                category = "adjustable_devices" if device_type == "AdjustableDevice" else "non_adjustable_devices"
                if category not in api_data:
                    api_data[category] = []
                api_data[category].append(device_api_data)

        # Dodaj podsumowanie decyzji algorytmu
        decision_summary = self.generate_decision_summary()
        api_data["algorithm_decision"] = decision_summary
        
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


    def generate_decision_summary(self):
        """Generuje bardzo zwięzłe podsumowanie decyzji algorytmu dla SCADA"""
        current_generation = self.microgrid.total_power_generated()
        current_consumption = self.consumergrid.total_power_consumed()
        energy_balance = current_generation - current_consumption
        
        # Użyj początkowego bilansu energetycznego do określenia przyczyny akcji
        initial_balance = getattr(self, 'initial_energy_balance', energy_balance)
        
        if not self.has_device_changes():
            return {
                "status": "OK",
                "message": "No action needed",
                "balance_kW": round(energy_balance, 1)
            }
        
        # Przeanalizuj główne typy zmian
        has_generation_changes = False
        has_storage_changes = False
        has_grid_trading = False
        has_consumption_changes = False
        
        for change in self.changed_devices:
            device_type = change["device_type"]
            action = change["action"]
            
            if device_type in ["PV", "WindTurbine", "FuelTurbine", "FuelCell"]:
                has_generation_changes = True
            elif device_type == "BESS":
                has_storage_changes = True
            elif device_type == "OSD":
                has_grid_trading = True
            elif device_type in ["AdjustableDevice", "NonAdjustableDevice"]:
                has_consumption_changes = True
        
        # Generuj bardzo krótki komunikat na podstawie POCZĄTKOWEGO bilansu
        if abs(initial_balance) > 50:  # Duża nierównowaga
            if initial_balance > 0:  # Była nadwyżka
                message = "Reduced generation"
                if has_storage_changes:
                    message = "Stored surplus"
                elif has_grid_trading:
                    message = "Sold to grid"
            else:  # Był deficyt
                message = "Increased generation"
                if has_storage_changes:
                    message = "Used battery"
                elif has_grid_trading:
                    message = "Bought from grid"
                elif has_consumption_changes:
                    message = "Reduced consumption"
        elif abs(initial_balance) > 10:  # Średnia nierównowaga
            message = "Minor adjustments"
        else:  # Mała nierównowaga
            message = "Fine tuning"
        
        # Status na podstawie końcowego bilansu (skuteczność)
        final_balance = abs(energy_balance)
        if final_balance < 10:
            status = "OK"
        elif final_balance < 50:
            status = "BALANCED"
        else:
            status = "ACTIVE"
        
        return {
            "status": status,
            "message": message,
            "balance_kW": round(initial_balance, 1),
            "devices_count": len(self.changed_devices)
        }
    
    def handle_triggered_events(self, events):
        """Obsługuje eventy triggered przez scheduler."""
        for event in events:
            self.info_logger.info(f"Handling event: {event.event_type} - {event.description}")
            
            if "bess" in event.event_type.lower():
                self.stop_bess_operation()  # ← SPRAWDŹ CZY TA FUNKCJA ISTNIEJE
            else:
                self.error_logger.warning(f"Unknown event type: {event.event_type}")
    
    def stop_bess_operation(self):
        """Zatrzymuje operację BESS (setpoint -> 0)."""
        if not self.microgrid.bess:
            return
        
        self.info_logger.info("🛑 Stopping BESS operation (setpoint -> 0 kW)")
        
        # Ustaw setpoint na 0
        self.microgrid.bess.setpoint_output = 0
        
        # Dodaj do changed_devices
        device_change = {
            "device": self.microgrid.bess,
            "action": "stop",
            "new_value": 0,
            "device_type": "BESS"
        }
        self.changed_devices.append(device_change)
        
        # Wyślij do API natychmiast
        if self.use_api and self.has_device_changes():
            api_changed_data = self.prepare_changed_devices_for_api()
            api_contract_data = self.prepare_contract_data_for_api()
            
            success = self.api_manager.send_updated_data_with_retry(
                api_changed_data,
                api_contract_data
            )
            
            if success:
                self.info_logger.info("✅ BESS stop command sent to SCADA")
            else:
                self.error_logger.error("❌ Failed to send BESS stop command")
    
    def log_grid_operations_for_scada(self):
        """
        Loguje operacje związane z siecią dla systemu SCADA.
        Wywołuj na końcu każdej iteracji.
        """
        export_setpoint = self.osd.get_current_grid_export()
        import_setpoint = self.osd.get_current_grid_import()
        
        if export_setpoint > 0:
            self.info_logger.important(
                f"🔋➡️🏭 SCADA GRID EXPORT: {export_setpoint:.2f} kW "
                f"(Total sold today: {self.osd.get_sold_power():.2f} kWh, "
                f"Remaining capacity: {self.osd.get_remaining_sale_capacity():.2f} kWh, "
                f"Sell price: {self.osd.get_current_sell_price():.3f} $/kWh)"
            )
        
        if import_setpoint > 0:
            self.info_logger.important(
                f"🏭➡️🔋 SCADA GRID IMPORT: {import_setpoint:.2f} kW "
                f"(Total bought today: {self.osd.get_bought_power():.2f} kWh, "
                f"Remaining capacity: {self.osd.get_remaining_purchase_capacity():.2f} kWh, "
                f"Buy price: {self.osd.get_current_buy_price():.3f} $/kWh)"
            )
        
        if export_setpoint == 0 and import_setpoint == 0:
            self.info_logger.info("SCADA GRID STATUS: No grid operations in this iteration")

    def _ensure_bess_checker(self):
        """
        Tworzy BESSCapabilityChecker jeśli BESS istnieje i checker jeszcze nie został utworzony.
        Lazy initialization - wywołuje się automatycznie po załadowaniu danych.
        """
        #self.info_logger.info("=" * 70)
        #self.info_logger.info("_ensure_bess_checker() CALLED")
        #self.info_logger.info(f"  self.microgrid.bess = {self.microgrid.bess}")
        #self.info_logger.info(f"  self.bess_checker = {self.bess_checker}")
        #self.info_logger.info(f"  Condition check: bess exists = {self.microgrid.bess is not None}, checker is None = {self.bess_checker is None}")
        #self.info_logger.info("=" * 70)
        
        if self.microgrid.bess and self.bess_checker is None:
            #self.info_logger.info("🔧 Creating BESSCapabilityChecker (lazy initialization)...")
            #self.info_logger.info(f"  BESS details: name={self.microgrid.bess.name}, max_charge={self.microgrid.bess.max_charge_level}")
            #self.info_logger.info(f"  auto_interval: {self.auto_interval}s")
            #self.info_logger.info(f"  iteration_duration: {self.auto_interval / 60:.2f} min")
            
            try:
                # ✅ DODAJ LOG PRZED IMPORTEM
                #self.info_logger.info("  Importing BESSCapabilityChecker...")
                from apps.backend.managment.bess_capability_checker import BESSCapabilityChecker
                #self.info_logger.info("  Import successful!")
                
                # ✅ DODAJ LOG PRZED TWORZENIEM
                #self.info_logger.info("  Creating BESSCapabilityChecker instance...")
                self.bess_checker = BESSCapabilityChecker(
                    bess=self.microgrid.bess,
                    iteration_time_minutes=self.auto_interval / 60,  # ✅ POPRAWIONE!
                    bess_low_threshold=0.20,  # ← DODAJ (20%)
                    info_logger=self.info_logger,
                    error_logger=self.error_logger
                )

                # ✅ DODAJ TE LOGI ZARAZ PO UTWORZENIU
                #self.info_logger.info(f"  Instance created! Type: {type(self.bess_checker)}")
                #self.info_logger.info(f"  Is None? {self.bess_checker is None}")
                #self.info_logger.info(f"  Value: {self.bess_checker}")

                if self.bess_checker is None:
                    self.error_logger.error("  ❌ BESSCapabilityChecker constructor returned None!")
                else:
                    self.info_logger.info(
                        f"✅ BESSCapabilityChecker initialized "
                        f"(BESS: {self.microgrid.bess.name}, "
                        f"iteration: {self.auto_interval/60:.2f} min, "
                        f"capacity: {self.microgrid.bess.max_charge_level:.0f} kWh)"
                    )
                
            except ImportError as e:
                self.error_logger.error(f"❌ IMPORT ERROR: {e}")
                self.error_logger.exception("Full traceback:")
            except AttributeError as e:
                self.error_logger.error(f"❌ ATTRIBUTE ERROR (prawdopodobnie brak atrybutu BESS): {e}")
                self.error_logger.exception("Full traceback:")
            except TypeError as e:
                self.error_logger.error(f"❌ TYPE ERROR (prawdopodobnie złe parametry): {e}")
                self.error_logger.exception("Full traceback:")
            except Exception as e:
                self.error_logger.error(f"❌ UNKNOWN ERROR: {type(e).__name__}: {e}")
                self.error_logger.exception("Full traceback:")
        
        elif self.bess_checker is not None:
            self.info_logger.info("ℹ️  BESSCapabilityChecker already exists, skipping creation")
        else:
            self.info_logger.warning("⚠️  No BESS available - BESSCapabilityChecker not created")
        
        # ✅ DODAJ LOG NA KOŃCU
        #self.info_logger.info(f"_ensure_bess_checker() FINISHED. self.bess_checker = {self.bess_checker}")


    def _load_bess_threshold(self):
        """Ładuje bess_low_threshold z pliku konfiguracyjnego."""
        # ← TUTAJ BRAKOWAŁO definicji config_path!
        config_path = os.path.join(self.base_path, "apps", "backend", "bess_config.json")
        
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
                threshold = config.get("bess_low_threshold", 0.20)
                
                self.info_logger.info(
                    f"✅ Loaded bess_low_threshold: {threshold*100:.0f}% from config file"
                )
                return threshold
                
        except FileNotFoundError:
            self.info_logger.warning(
                f"⚠️  BESS config file not found at {config_path}. Using default: 20%"
            )
            return 0.20
            
        except Exception as e:
            self.error_logger.error(f"❌ Error loading BESS config: {e}. Using default: 20%")
            return 0.20
        
    def calculate_energy_balance(self) -> EnergyBalance:
        """
        Oblicza rzeczywisty bilans energetyczny mikrosieci.
        
        ✅ POPRAWIONA WERSJA - uwzględnia:
        - Generację (PV, Wind, Fuel Turbine, Fuel Cell)
        - BESS (rozładowanie/ładowanie) - używa actual_output
        - Grid (import/export) - używa current_grid_import/export
        - Zużycie (odbiorniki)
        
        Returns:
            EnergyBalance: Szczegółowy bilans energetyczny
        """
        
        # ====================================================================
        # SUPPLY SIDE (źródła energii)
        # ====================================================================
        
        # 1. Generacja ze źródeł (PV, Wind, Fuel Turbine, Fuel Cell)
        generation = 0.0
        for device in self.microgrid.get_all_devices():
            if device.get_switch_status():
                generation += device.get_actual_output()
        
        # 2. Grid import (kupno energii z sieci)
        # ✅ POPRAWKA: Użyj actual_grid_import (rzeczywisty stan)
        grid_import = self.osd.actual_grid_import
        
        # 3. BESS discharge (rozładowanie baterii)
        # ⚠️ WAŻNE: actual_output > 0 → BESS dostarcza energię (rozładowanie)
        bess_discharge = 0.0
        if self.microgrid.bess and self.microgrid.bess.actual_output > 0:
            bess_discharge = self.microgrid.bess.actual_output
        
        # Suma podaży
        total_supply = generation + grid_import + bess_discharge
        
        # ====================================================================
        # DEMAND SIDE (odbiorniki energii)
        # ====================================================================
        
        # 1. Zużycie odbiorników (loads)
        consumption = 0.0
        for device in (
            self.consumergrid.adjustable_devices +
            self.consumergrid.non_adjustable_devices
        ):
            if device.switch_status:
                # ✅ DODAJ DEBUG:
                self.info_logger.debug(
                    f"   🔍 DEBUG: {device.name} consumption: {device.power:.2f} kW"
                )
                consumption += device.get_current_power()
        
        # 2. Grid export (sprzedaż energii do sieci)
        # ✅ POPRAWKA: Użyj actual_grid_export (rzeczywisty stan)
        grid_export = self.osd.actual_grid_export
        
        # 3. BESS charge (ładowanie baterii)
        # ⚠️ WAŻNE: actual_output < 0 → BESS pobiera energię (ładowanie)
        bess_charge = 0.0
        if self.microgrid.bess and self.microgrid.bess.actual_output < 0:
            bess_charge = abs(self.microgrid.bess.actual_output)  # Zamień na wartość dodatnią
        
        # Suma popytu
        total_demand = consumption + grid_export + bess_charge
        
        # ====================================================================
        # BILANS
        # ====================================================================
        
        balance = total_supply - total_demand
        
        # Stwórz obiekt EnergyBalance
        energy_balance = EnergyBalance(
            generation=generation,
            grid_import=grid_import,
            bess_discharge=bess_discharge,
            consumption=consumption,
            grid_export=grid_export,
            bess_charge=bess_charge,
            total_supply=total_supply,
            total_demand=total_demand,
            balance=balance
        )
        
        # Loguj szczegółowy bilans
        self._log_energy_balance(energy_balance)
        
        return energy_balance
    
    # apps/backend/managment/energy_manager_class.py

    def _log_energy_balance(self, balance: EnergyBalance):
        """
        Loguje szczegółowy bilans energetyczny.
        UPROSZCZONA WERSJA - czytelniejsze formatowanie.
        """
        self.info_logger.info("")
        self.info_logger.info("⚖️  ENERGY BALANCE")
        self.info_logger.info("-" * 70)
        
        # Supply side - w jednej linii
        self.info_logger.info(
            f"Supply:  Gen={balance.generation:.2f} + "
            f"Grid_In={balance.grid_import:.2f} + "
            f"BESS_Out={balance.bess_discharge:.2f} = "
            f"{balance.total_supply:.2f} kW"
        )
        
        # Demand side - w jednej linii
        self.info_logger.info(
            f"Demand:  Con={balance.consumption:.2f} + "
            f"Grid_Out={balance.grid_export:.2f} + "
            f"BESS_In={balance.bess_charge:.2f} = "
            f"{balance.total_demand:.2f} kW"
        )
        
        # Balance status
        if balance.is_balanced():
            status_emoji = "⚖️"
            status_text = "BALANCED"
        elif balance.has_surplus:
            status_emoji = "⚡"
            status_text = f"SURPLUS {balance.surplus:.2f} kW"
        else:
            status_emoji = "📉"
            status_text = f"DEFICIT {balance.deficit:.2f} kW"
        
        self.info_logger.important(
            f"Balance: {balance.balance:+.2f} kW → {status_emoji} {status_text}"
        )
        self.info_logger.info("-" * 70)


    def _log_initial_system_status(self):
        """
        Loguje POCZĄTKOWY status systemu (przed działaniami algorytmu).
        Wywołuj RAZ na początku iteracji.
        """
        self.info_logger.info("")
        self.info_logger.info("📊 INITIAL SYSTEM STATUS")
        self.info_logger.info("-" * 70)
        
        total_generated = self.microgrid.total_power_generated()
        total_consumed = self.consumergrid.total_power_consumed()
        
        self.info_logger.info(f"Generation:  {total_generated:>8.2f} kW")
        self.info_logger.info(f"Consumption: {total_consumed:>8.2f} kW")
        
        # BESS status
        if self.microgrid.bess:
            bess = self.microgrid.bess
            self.info_logger.info(
                f"BESS:        {bess.charge_level:>8.2f}/{bess.capacity:.2f} kWh "
                f"(actual: {bess.actual_output:+.2f} kW)"
            )
        
        # Grid status
        self.info_logger.info(
            f"Grid:        Import={self.osd.current_grid_import:.2f} kW, "
            f"Export={self.osd.current_grid_export:.2f} kW"
        )
        
        # Trading status
        self.info_logger.info(
            f"Trading:     Sold={self.osd.sold_power:.2f}/{self.osd.CONTRACTED_SALE_LIMIT:.2f} kWh, "
            f"Bought={self.osd.bought_power:.2f}/{self.osd.CONTRACTED_PURCHASE_LIMIT:.2f} kWh"
        )
        
        self.info_logger.info("-" * 70)


    def _log_final_system_status(self):
        """
        Loguje KOŃCOWY status systemu (po działaniach algorytmu).
        Wywołuj TYLKO jeśli były zmiany.
        """
        self.info_logger.info("")
        self.info_logger.info("📊 FINAL SYSTEM STATUS (after algorithm actions)")
        self.info_logger.info("-" * 70)
        
        total_generated = self.microgrid.total_power_generated()
        total_consumed = self.consumergrid.total_power_consumed()
        
        self.info_logger.info(f"Generation:  {total_generated:>8.2f} kW")
        self.info_logger.info(f"Consumption: {total_consumed:>8.2f} kW")
        
        # BESS status
        if self.microgrid.bess:
            bess = self.microgrid.bess
            self.info_logger.info(
                f"BESS:        {bess.charge_level:>8.2f}/{bess.capacity:.2f} kWh "
                f"(setpoint: {bess.setpoint_output:+.2f} kW)"
            )
        
        # Grid status
        if self.osd.current_grid_export > 0 or self.osd.current_grid_import > 0:
            self.info_logger.info(
                f"Grid:        Import={self.osd.current_grid_import:.2f} kW, "
                f"Export={self.osd.current_grid_export:.2f} kW"
            )
        
        # Zmiany
        if self.changed_devices:
            self.info_logger.info(f"Changes:     {len(self.changed_devices)} device(s) modified")
            for change in self.changed_devices[:5]:  # Pokaż max 5
                device = change["device"]
                action = change["action"]
                self.info_logger.info(f"  • {device.name}: {action}")
            if len(self.changed_devices) > 5:
                self.info_logger.info(f"  ... and {len(self.changed_devices) - 5} more")
        
        self.info_logger.info("-" * 70)

    # apps/backend/managment/energy_manager_class.py

    # =========================================================================
    # ETAP 1: NEUTRALIZACJA KONFLIKTOWYCH OPERACJI
    # =========================================================================

    def _log_operator_summary(self, 
                             initial_balance: EnergyBalance,
                             final_balance: EnergyBalance,
                             actions_taken: list,
                             decision_rationale: str = None):
        """
        Loguje profesjonalne podsumowanie dla operatorów.
        
        Args:
            initial_balance: Bilans przed akcjami
            final_balance: Bilans po akcjach
            actions_taken: Lista podjętych akcji
            decision_rationale: Uzasadnienie decyzji (opcjonalne)
        """
        from datetime import datetime
        
        self.info_logger.info("")
        self.info_logger.info("=" * 70)
        self.info_logger.info(f"ITERATION SUMMARY - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.info_logger.info("=" * 70)
        
        # ═══════════════════════════════════════════════════════════
        # SEKCJA 1: STAN SYSTEMU
        # ═══════════════════════════════════════════════════════════
        self.info_logger.info("")
        self.info_logger.info("┌" + "─" * 68 + "┐")
        self.info_logger.info("│ 1. SYSTEM STATE" + " " * 50 + "│")
        self.info_logger.info("└" + "─" * 68 + "┘")
        
        total_gen = self.microgrid.total_power_generated()
        total_cons = self.consumergrid.total_power_consumed()
        
        self.info_logger.info(f"  Generation:     {total_gen:>8.2f} kW")
        self.info_logger.info(f"  Consumption:    {total_cons:>8.2f} kW")
        
        if self.microgrid.bess:
            bess = self.microgrid.bess
            soc_pct = (bess.charge_level / bess.capacity) * 100
            op_type = "CHARGING" if bess.actual_output < 0 else "DISCHARGING" if bess.actual_output > 0 else "IDLE"
            self.info_logger.info(f"  BESS:           {bess.charge_level:>8.2f}/{bess.capacity:.2f} kWh ({soc_pct:.0f}% SOC) - {op_type}")
        
        if self.osd.actual_grid_export > 0 or self.osd.actual_grid_import > 0:
            if self.osd.actual_grid_export > 0:
                self.info_logger.info(f"  Grid:           EXPORTING {self.osd.actual_grid_export:.2f} kW")
            if self.osd.actual_grid_import > 0:
                self.info_logger.info(f"  Grid:           IMPORTING {self.osd.actual_grid_import:.2f} kW")
        
        # ═══════════════════════════════════════════════════════════
        # SEKCJA 2: ANALIZA BILANSU
        # ═══════════════════════════════════════════════════════════
        self.info_logger.info("")
        self.info_logger.info("┌" + "─" * 68 + "┐")
        self.info_logger.info("│ 2. ENERGY BALANCE ANALYSIS" + " " * 42 + "│")
        self.info_logger.info("└" + "─" * 68 + "┘")
        
        # Porównanie bilansów
        balance_change = final_balance.balance - initial_balance.balance
        self.info_logger.info(f"  Initial Balance:  {initial_balance.balance:+.2f} kW")
        self.info_logger.info(f"  Final Balance:    {final_balance.balance:+.2f} kW")
        self.info_logger.info(f"  Balance Change:   {balance_change:+.2f} kW")
        
        if abs(balance_change) > 0.1:
            if balance_change > 0:
                self.info_logger.info(f"  Status: ✅ IMPROVED (reduced deficit or increased surplus)")
            else:
                self.info_logger.info(f"  Status: ⚠️  WORSENED (increased deficit or reduced surplus)")
        else:
            self.info_logger.info(f"  Status: ➡️  STABLE (minimal change)")
        
        self.info_logger.info(
            f"  Supply Side:    {initial_balance.generation:.2f} kW (Gen) + "
            f"{initial_balance.grid_import:.2f} kW (Grid) + "
            f"{initial_balance.bess_discharge:.2f} kW (BESS) = {initial_balance.total_supply:.2f} kW"
        )
        self.info_logger.info(
            f"  Demand Side:    {initial_balance.consumption:.2f} kW (Load) + "
            f"{initial_balance.grid_export:.2f} kW (Export) + "
            f"{initial_balance.bess_charge:.2f} kW (BESS) = {initial_balance.total_demand:.2f} kW"
        )
        self.info_logger.info("  " + "─" * 66)
        
        if initial_balance.has_deficit:
            status_icon = "📉"
            status_text = f"{initial_balance.deficit:.2f} kW DEFICIT"
        elif initial_balance.has_surplus:
            status_icon = "⚡"
            status_text = f"{initial_balance.surplus:.2f} kW SURPLUS"
        else:
            status_icon = "⚖️"
            status_text = "BALANCED"
        
        self.info_logger.info(f"  IMBALANCE:      {initial_balance.balance:+.2f} kW {status_icon} {status_text}")
        
        # ═══════════════════════════════════════════════════════════
        # SEKCJA 3: PODJĘTE AKCJE (jeśli były)
        # ═══════════════════════════════════════════════════════════
        if actions_taken:
            self.info_logger.info("")
            self.info_logger.info("┌" + "─" * 68 + "┐")
            self.info_logger.info("│ 3. CORRECTIVE ACTIONS" + " " * 47 + "│")
            self.info_logger.info("└" + "─" * 68 + "┘")
            
            # Grupuj akcje według typu
            action_groups = {}
            for action in actions_taken:
                action_type = action.get('action', 'unknown')
                if action_type not in action_groups:
                    action_groups[action_type] = []
                action_groups[action_type].append(action)
            
            for action_type, actions in action_groups.items():
                if action_type == "stop_charging":
                    self.info_logger.info(f"  • Neutralized BESS charging ({len(actions)} action(s))")
                elif action_type == "stop_discharging":
                    self.info_logger.info(f"  • Neutralized BESS discharging ({len(actions)} action(s))")
                elif action_type == "stop_export":
                    self.info_logger.info(f"  • Neutralized Grid export ({len(actions)} action(s))")
                elif action_type == "stop_import":
                    self.info_logger.info(f"  • Neutralized Grid import ({len(actions)} action(s))")
                elif "increase_output" in action_type:
                    self.info_logger.info(f"  • Increased generator output ({len(actions)} action(s))")
                elif "restore_consumer" in action_type:
                    self.info_logger.info(f"  • Restored disabled consumers ({len(actions)} action(s))")
                else:
                    self.info_logger.info(f"  • {action_type.replace('_', ' ').title()} ({len(actions)} action(s))")
        
        # ═══════════════════════════════════════════════════════════
        # SEKCJA 4: WYNIK KOŃCOWY
        # ═══════════════════════════════════════════════════════════
        if actions_taken:
            self.info_logger.info("┌" + "─" * 68 + "┐")
            self.info_logger.info("│ 4. POST-ACTION BALANCE" + " " * 46 + "│")
            self.info_logger.info("└" + "─" * 68 + "┘")
            
            self.info_logger.info(
                f"  Supply Side:    {final_balance.generation:.2f} kW (Gen) + "
                f"{final_balance.grid_import:.2f} kW (Grid) + "
                f"{final_balance.bess_discharge:.2f} kW (BESS) = {final_balance.total_supply:.2f} kW"
            )
            self.info_logger.info(
                f"  Demand Side:    {final_balance.consumption:.2f} kW (Load) + "
                f"{final_balance.grid_export:.2f} kW (Export) + "
                f"{final_balance.bess_charge:.2f} kW (BESS) = {final_balance.total_demand:.2f} kW"
            )
            self.info_logger.info("  " + "─" * 66)
            
            if final_balance.is_balanced():
                self.info_logger.info(f"  RESULT:         {final_balance.balance:+.2f} kW ⚖️  BALANCED ✓")
            else:
                remaining = "SURPLUS" if final_balance.has_surplus else "DEFICIT"
                amount = final_balance.surplus if final_balance.has_surplus else final_balance.deficit
                self.info_logger.info(f"  RESULT:         {final_balance.balance:+.2f} kW ({amount:.2f} kW {remaining} remaining)")
        
        # ═══════════════════════════════════════════════════════════
        # SEKCJA 5: UZASADNIENIE DECYZJI
        # ═══════════════════════════════════════════════════════════
        self.info_logger.info("")
        self.info_logger.info("┌" + "─" * 68 + "┐")
        self.info_logger.info("│ 5. DECISION RATIONALE" + " " * 45 + "│")
        self.info_logger.info("└" + "─" * 68 + "┘")
        
        if decision_rationale:
            self.info_logger.info(f"  {decision_rationale}")
        else:
            self.info_logger.info("  No specific rationale provided.")
        
        # Dodatkowe szczegóły o decyzjach
        if actions_taken:
            self.info_logger.info("")
            self.info_logger.info("  DECISION BREAKDOWN:")
            
            # Grupuj akcje według typu
            action_groups = {}
            for action in actions_taken:
                action_type = action.get("action", "unknown")
                if action_type not in action_groups:
                    action_groups[action_type] = []
                action_groups[action_type].append(action)
            
            for action_type, actions in action_groups.items():
                if action_type == "stop_charging":
                    self.info_logger.info(f"    • Neutralized BESS charging ({len(actions)} action(s))")
                elif action_type == "stop_discharging":
                    self.info_logger.info(f"    • Neutralized BESS discharging ({len(actions)} action(s))")
                elif action_type == "stop_export":
                    self.info_logger.info(f"    • Neutralized Grid export ({len(actions)} action(s))")
                elif action_type == "stop_import":
                    self.info_logger.info(f"    • Neutralized Grid import ({len(actions)} action(s))")
                elif "increase_output" in action_type:
                    self.info_logger.info(f"    • Increased generator output ({len(actions)} action(s))")
                elif "restore_consumer" in action_type:
                    self.info_logger.info(f"    • Restored disabled consumers ({len(actions)} action(s))")
                else:
                    self.info_logger.info(f"    • {action_type.replace('_', ' ').title()} ({len(actions)} action(s))")
        
        # ═══════════════════════════════════════════════════════════
        # SEKCJA 6: PODSUMOWANIE
        # ═══════════════════════════════════════════════════════════
        self.info_logger.info("")
        self.info_logger.info("┌" + "─" * 68 + "┐")
        self.info_logger.info("│ 6. SUMMARY" + " " * 58 + "│")
        self.info_logger.info("└" + "─" * 68 + "┘")
        
        if final_balance.is_balanced():
            self.info_logger.info("  Status:         ✓ BALANCED - No further action required")
        else:
            if final_balance.has_surplus:
                self.info_logger.info(f"  Status:         ⚡ {final_balance.surplus:.2f} kW surplus managed")
            else:
                self.info_logger.info(f"  Status:         📉 {final_balance.deficit:.2f} kW deficit managed")
        
        if actions_taken:
            self.info_logger.info(f"  Changes Made:   {len(actions_taken)} device(s) modified")
            for action in actions_taken[:3]:  # Pokaż max 3
                device = action.get('device')
                action_type = action.get('action', '')
                device_name = device.name if hasattr(device, 'name') else str(device)
                self.info_logger.info(f"    • {device_name}: {action_type.replace('_', ' ')}")
            if len(actions_taken) > 3:
                self.info_logger.info(f"    ... and {len(actions_taken) - 3} more")
        
        # Decyzja (jeśli była)
        if decision_rationale:
            self.info_logger.info(f"  Decision:       {decision_rationale}")
        
        next_time = datetime.now().replace(second=0, microsecond=0)
        # Dodaj 5 minut
        from datetime import timedelta
        next_time = next_time + timedelta(minutes=5)
        self.info_logger.info(f"  Next Iteration: {next_time.strftime('%Y-%m-%d %H:%M:%S')} (in 5 minutes)")
        
        self.info_logger.info("")
        self.info_logger.info("=" * 70)
    
    def neutralize_conflicting_operations(self, balance: EnergyBalance) -> EnergyBalance:
        """
        Neutralizuje operacje, które POWODUJĄ deficyt/nadwyżkę.
        
        KLUCZOWA FUNKCJA - wywołuj PRZED manage_surplus/deficit!
        
        ✅ Z SYMULACJĄ: Zmienia zarówno setpoint (dla SCADA) jak i actual (dla obliczeń)
        
        Args:
            balance: Obecny bilans energetyczny
            
        Returns:
            EnergyBalance: Zaktualizowany bilans po neutralizacji
        """
        self.info_logger.info("")
        self.info_logger.info("🔍 ANALYZING CONFLICTING OPERATIONS")
        self.info_logger.info("-" * 70)
        
        neutralized = False
        neutralized_amount = 0.0
        
        # === DEFICYT - szukaj operacji, które ZWIĘKSZAJĄ zapotrzebowanie ===
        if balance.has_deficit:
            self.info_logger.info(f"Deficit detected: {balance.deficit:.2f} kW")
            
            # 1. BESS ładuje się? (pobiera energię)
            if self.microgrid.bess and self.microgrid.bess.actual_output < 0:
                bess_charging = abs(self.microgrid.bess.actual_output)
                self.info_logger.warning(
                    f"⚠️  BESS is CHARGING {bess_charging:.2f} kW → CAUSING deficit!"
                )
                self.info_logger.info(f"   → NEUTRALIZING: Stop BESS charging")
                
                # Zapisz poprzedni stan (dla logowania)
                previous_actual = self.microgrid.bess.actual_output
                previous_setpoint = self.microgrid.bess.setpoint_output
                
                # ═══════════════════════════════════════════════════════════
                # KROK A: Ustaw setpoint (POLECENIE dla SCADA)
                # ═══════════════════════════════════════════════════════════
                self.microgrid.bess.setpoint_output = 0
                self.info_logger.info(f"   ✓ Set setpoint_output = 0 kW (command for SCADA)")
                
                # ═══════════════════════════════════════════════════════════
                # KROK B: Symuluj actual_output (TYLKO dla obliczeń w Pythonie)
                # ═══════════════════════════════════════════════════════════
                self.simulate_device_state_for_calculations(
                    self.microgrid.bess, 
                    "stop_charging", 
                    0
                )
                self.info_logger.info(f"   ✓ Simulated actual_output = 0 kW (for calculations only)")
                
                # Dodaj do changed_devices
                device_change = {
                    "device": self.microgrid.bess,
                    "action": "stop_charging",
                    "previous_value": previous_setpoint,
                    "new_value": 0,
                    "device_type": "BESS"
                }
                self.changed_devices.append(device_change)
                
                neutralized = True
                neutralized_amount += bess_charging
            
            # 2. Grid eksportuje? (traci energię)
            if self.osd.actual_grid_export > 0:  # ✅ Zmiana: actual zamiast current
                grid_exporting = self.osd.actual_grid_export
                self.info_logger.warning(
                    f"⚠️  GRID is EXPORTING {grid_exporting:.2f} kW → CAUSING deficit!"
                )
                self.info_logger.info(f"   → NEUTRALIZING: Stop grid export")
                
                # Zapisz poprzedni stan
                previous_actual = self.osd.actual_grid_export
                previous_setpoint = self.osd.setpoint_grid_export
                
                # ═══════════════════════════════════════════════════════════
                # KROK A: Ustaw setpoint (POLECENIE dla SCADA)
                # ═══════════════════════════════════════════════════════════
                self.osd.setpoint_grid_export = 0
                self.info_logger.info(f"   ✓ Set setpoint_grid_export = 0 kW (command for SCADA)")
                
                # ═══════════════════════════════════════════════════════════
                # KROK B: Symuluj actual (TYLKO dla obliczeń w Pythonie)
                # ═══════════════════════════════════════════════════════════
                self.simulate_device_state_for_calculations(
                    self.osd, 
                    "stop_export", 
                    0
                )
                self.info_logger.info(f"   ✓ Simulated actual_grid_export = 0 kW (for calculations only)")
                
                # Backward compatibility (tymczasowo)
                self.osd.current_grid_export = 0
                
                # Dodaj do changed_devices
                device_change = {
                    "device": self.osd,
                    "action": "stop_export",
                    "previous_value": previous_setpoint,
                    "new_value": 0,
                    "device_type": "OSD"
                }
                self.changed_devices.append(device_change)
                
                neutralized = True
                neutralized_amount += grid_exporting
            
            # 3. Generatory niepotrzebnie ograniczone? (krok 5 scenariusza)
            self.info_logger.info("🔍 Checking for unnecessarily limited generators...")
            generators_freed = self._check_and_free_limited_generators(balance.deficit)
            if generators_freed > 0:
                neutralized = True
                neutralized_amount += generators_freed
                self.info_logger.info(f"   ✓ Freed {generators_freed:.2f} kW from limited generators")
        
        # === NADWYŻKA - szukaj operacji, które ZWIĘKSZAJĄ produkcję ===
        elif balance.has_surplus:
            self.info_logger.info(f"Surplus detected: {balance.surplus:.2f} kW")
            
            # 1. BESS rozładowuje się? (dostarcza energię)
            if self.microgrid.bess and self.microgrid.bess.actual_output > 0:
                bess_discharging = self.microgrid.bess.actual_output
                self.info_logger.warning(
                    f"⚠️  BESS is DISCHARGING {bess_discharging:.2f} kW → CAUSING surplus!"
                )
                self.info_logger.info(f"   → NEUTRALIZING: Stop BESS discharging")
                
                # Zapisz poprzedni stan
                previous_actual = self.microgrid.bess.actual_output
                previous_setpoint = self.microgrid.bess.setpoint_output
                
                # ═══════════════════════════════════════════════════════════
                # KROK A: Ustaw setpoint (POLECENIE dla SCADA)
                # ═══════════════════════════════════════════════════════════
                self.microgrid.bess.setpoint_output = 0
                self.info_logger.info(f"   ✓ Set setpoint_output = 0 kW (command for SCADA)")
                
                # ═══════════════════════════════════════════════════════════
                # KROK B: Symuluj actual_output (TYLKO dla obliczeń w Pythonie)
                # ═══════════════════════════════════════════════════════════
                self.simulate_device_state_for_calculations(
                    self.microgrid.bess, 
                    "stop_discharging", 
                    0
                )
                self.info_logger.info(f"   ✓ Simulated actual_output = 0 kW (for calculations only)")
                
                # Dodaj do changed_devices
                device_change = {
                    "device": self.microgrid.bess,
                    "action": "stop_discharging",
                    "previous_value": previous_setpoint,
                    "new_value": 0,
                    "device_type": "BESS"
                }
                self.changed_devices.append(device_change)
                
                neutralized = True
                neutralized_amount += bess_discharging
            
            # 2. Grid importuje? (dodaje energię)
            if self.osd.actual_grid_import > 0:  # ✅ Zmiana: actual zamiast current
                grid_importing = self.osd.actual_grid_import
                self.info_logger.warning(
                    f"⚠️  GRID is IMPORTING {grid_importing:.2f} kW → CAUSING surplus!"
                )
                self.info_logger.info(f"   → NEUTRALIZING: Stop grid import")
                
                # Zapisz poprzedni stan
                previous_actual = self.osd.actual_grid_import
                previous_setpoint = self.osd.setpoint_grid_import
                
                # ═══════════════════════════════════════════════════════════
                # KROK A: Ustaw setpoint (POLECENIE dla SCADA)
                # ═══════════════════════════════════════════════════════════
                self.osd.setpoint_grid_import = 0
                self.info_logger.info(f"   ✓ Set setpoint_grid_import = 0 kW (command for SCADA)")
                
                # ═══════════════════════════════════════════════════════════
                # KROK B: Symuluj actual (TYLKO dla obliczeń w Pythonie)
                # ═══════════════════════════════════════════════════════════
                self.simulate_device_state_for_calculations(
                    self.osd, 
                    "stop_import", 
                    0
                )
                self.info_logger.info(f"   ✓ Simulated actual_grid_import = 0 kW (for calculations only)")
                
                # Backward compatibility (tymczasowo)
                self.osd.current_grid_import = 0
                
                # Dodaj do changed_devices
                device_change = {
                    "device": self.osd,
                    "action": "stop_import",
                    "previous_value": previous_setpoint,
                    "new_value": 0,
                    "device_type": "OSD"
                }
                self.changed_devices.append(device_change)
                
                neutralized = True
                neutralized_amount += grid_importing
            
            # 3. Odbiorniki niepotrzebnie wyłączone? (krok 5 scenariusza)
            self.info_logger.info("🔍 Checking for unnecessarily disabled consumers...")
            consumers_restored = self._check_and_restore_disabled_consumers(balance.surplus)
            if consumers_restored > 0:
                neutralized = True
                neutralized_amount += consumers_restored
                self.info_logger.info(f"   ✓ Restored {consumers_restored:.2f} kW from disabled consumers")
        
        if neutralized:
            self.info_logger.info("")
            self.info_logger.info(f"✓ Neutralized {neutralized_amount:.2f} kW of conflicting operations")
            self.info_logger.info("   Recalculating balance with simulated state...")
            
            # ═══════════════════════════════════════════════════════════════
            # PRZELICZ BILANS PONOWNIE (używa ZSYMULOWANEGO actual_output!)
            # ═══════════════════════════════════════════════════════════════
            new_balance = self.calculate_energy_balance()
            
            self.info_logger.info(
                f"   New balance: {new_balance.balance:+.2f} kW "
                f"(was: {balance.balance:+.2f} kW, delta: {new_balance.balance - balance.balance:+.2f} kW)"
            )
            
            return new_balance
        else:
            self.info_logger.info("✓ No conflicting operations detected")
            return balance
    
    def check_device_already_operating(self, device_type: str, operation: str) -> tuple:
        """
        Sprawdza czy urządzenie już wykonuje daną operację.
        
        Args:
            device_type: "BESS" lub "GRID"
            operation: "charging", "discharging", "importing", "exporting"
            
        Returns:
            tuple: (is_operating: bool, current_amount: float)
        """
        if device_type == "BESS":
            if not self.microgrid.bess:
                return False, 0.0
            
            if operation == "charging":
                if self.microgrid.bess.actual_output < 0:
                    return True, abs(self.microgrid.bess.actual_output)
                return False, 0.0
            
            elif operation == "discharging":
                if self.microgrid.bess.actual_output > 0:
                    return True, self.microgrid.bess.actual_output
                return False, 0.0
        
        elif device_type == "GRID":
            if operation == "importing":
                # ✅ POPRAWKA: Użyj actual_grid_import
                if self.osd.actual_grid_import > 0:
                    return True, self.osd.actual_grid_import
                return False, 0.0
            
            elif operation == "exporting":
                # ✅ POPRAWKA: Użyj actual_grid_export
                if self.osd.actual_grid_export > 0:
                    return True, self.osd.actual_grid_export
                return False, 0.0
        
        return False, 0.0
    
    def _check_and_free_limited_generators(self, deficit: float) -> float:
        """
        Sprawdza i zwalnia niepotrzebnie ograniczone generatory.
        
        Args:
            deficit: Aktualny deficyt energii (kW)
            
        Returns:
            float: Ilość uwolnionej energii (kW)
        """
        freed_power = 0.0
        
        # Pobierz wszystkie generatory
        all_generators = (
            self.microgrid.pv_panels +
            self.microgrid.wind_turbines +
            self.microgrid.fuel_turbines +
            self.microgrid.fuel_cells
        )
        
        for generator in all_generators:
            if not generator.get_switch_status():
                continue  # Pomiń nieaktywne generatory
                
            current_output = generator.get_actual_output()
            max_output = generator.get_max_output()
            
            # Sprawdź czy generator może produkować więcej
            if current_output < max_output - self.EPSILON:
                potential_increase = max_output - current_output
                increase_needed = min(potential_increase, deficit - freed_power)
                
                if increase_needed > self.EPSILON:
                    self.info_logger.info(
                        f"   🔧 Generator {generator.name}: {current_output:.2f} → {current_output + increase_needed:.2f} kW "
                        f"(+{increase_needed:.2f} kW)"
                    )
                    
                    # Zwiększ moc generatora
                    if generator.is_adjustable:
                        new_output = current_output + increase_needed
                        if generator.set_output(new_output):
                            freed_power += increase_needed
                            
                            # Dodaj do changed_devices
                            device_change = {
                                "device": generator,
                                "action": f"increase_output:{new_output}",
                                "previous_value": current_output,
                                "new_value": increase_needed,
                                "device_type": self.get_device_type(generator)
                            }
                            self.changed_devices.append(device_change)
                            
                            self.info_logger.info(f"   ✓ Increased {generator.name} by {increase_needed:.2f} kW")
                    
                    if freed_power >= deficit - self.EPSILON:
                        break  # Wystarczająco uwolniono
        
        return freed_power
    
    def _check_and_restore_disabled_consumers(self, surplus: float) -> float:
        """
        Sprawdza i przywraca niepotrzebnie wyłączone odbiorniki.
        
        Args:
            surplus: Aktualna nadwyżka energii (kW)
            
        Returns:
            float: Ilość przywróconej energii (kW)
        """
        restored_power = 0.0
        
        # Pobierz wszystkie odbiorniki
        all_consumers = (
            self.consumergrid.adjustable_devices +
            self.consumergrid.non_adjustable_devices
        )
        
        # Sortuj według priorytetu (malejąco - najpierw najważniejsze)
        all_consumers.sort(key=lambda x: x.priority, reverse=True)
        
        for consumer in all_consumers:
            if consumer.get_switch_status():
                continue  # Pomiń aktywne odbiorniki
                
            max_power = consumer.get_max_output() if hasattr(consumer, 'get_max_output') else consumer.max_power
            
            # Sprawdź czy odbiornik może być włączony
            if max_power > self.EPSILON:
                power_to_restore = min(max_power, surplus - restored_power)
                
                if power_to_restore > self.EPSILON:
                    self.info_logger.info(
                        f"   🔧 Consumer {consumer.name}: OFF → ON ({power_to_restore:.2f} kW)"
                    )
                    
                    # Włącz odbiornik
                    if consumer.activate():
                        if consumer.is_adjustable and hasattr(consumer, 'set_output'):
                            consumer.set_output(power_to_restore)
                        else:
                            consumer.power = power_to_restore
                        
                        restored_power += power_to_restore
                        
                        # Dodaj do changed_devices
                        device_change = {
                            "device": consumer,
                            "action": f"restore_consumer:{power_to_restore}",
                            "previous_value": 0,
                            "new_value": power_to_restore,
                            "device_type": self.get_device_type(consumer)
                        }
                        self.changed_devices.append(device_change)
                        
                        self.info_logger.info(f"   ✓ Restored {consumer.name} with {power_to_restore:.2f} kW")
                    
                    if restored_power >= surplus - self.EPSILON:
                        break  # Wystarczająco przywrócono
        
        return restored_power
    
    def _log_initial_state(self, balance: EnergyBalance):
        """Loguje stan początkowy systemu"""
        self.info_logger.info("DEBUG: _log_initial_state called")
        self.info_logger.info("DEBUG: balance.balance = " + str(balance.balance))
        self.info_logger.info("DEBUG: balance.total_supply = " + str(balance.total_supply))
        self.info_logger.info("DEBUG: balance.total_demand = " + str(balance.total_demand))
        self.info_logger.info("")
        self.info_logger.info("INITIAL STATE")
        self.info_logger.info("-" * 30)
        self.info_logger.info(f"⚖️  Balance: {balance.balance:+.2f} kW {'(SURPLUS)' if balance.has_surplus else '(DEFICIT)' if balance.has_deficit else '(BALANCED)'}")
        self.info_logger.info(f"📈 Supply:  {balance.total_supply:.2f} kW (Gen: {balance.generation:.1f}, Grid: {balance.grid_import:.1f}, BESS: {balance.bess_discharge:.1f})")
        self.info_logger.info(f"📉 Demand:  {balance.total_demand:.2f} kW (Load: {balance.consumption:.1f}, Export: {balance.grid_export:.1f}, BESS: {balance.bess_charge:.1f})")
        
        # BESS tylko jeśli aktywny
        if self.microgrid.bess and self.microgrid.bess.actual_output != 0:
            bess = self.microgrid.bess
            charge_percent = ((bess.charge_level - bess.min_charge_level) / (bess.max_charge_level - bess.min_charge_level)) * 100
            self.info_logger.info(f"🔋 BESS: {bess.charge_level:.1f}/{bess.max_charge_level:.1f} kWh ({charge_percent:.0f}%) | {bess.actual_output:+.1f} kW")
        
        # Grid tylko jeśli aktywny
        if self.osd.actual_grid_import > 0 or self.osd.actual_grid_export > 0:
            self.info_logger.info(f"🌐 GRID: Import={self.osd.actual_grid_import:.1f} kW, Export={self.osd.actual_grid_export:.1f} kW")
    
    def _log_after_neutralization(self, balance: EnergyBalance):
        """Loguje stan po neutralizacji konfliktów"""
        self.info_logger.info("")
        self.info_logger.info("🔧 AFTER NEUTRALIZATION")
        self.info_logger.info("-" * 30)
        self.info_logger.info(f"⚖️  Balance: {balance.balance:+.2f} kW {'(SURPLUS)' if balance.has_surplus else '(DEFICIT)' if balance.has_deficit else '(BALANCED)'}")
        self.info_logger.info(f"📈 Supply:  {balance.total_supply:.2f} kW")
        self.info_logger.info(f"📉 Demand:  {balance.total_demand:.2f} kW")
    
    def _log_final_state(self, balance: EnergyBalance):
        """Loguje stan końcowy systemu"""
        self.info_logger.info("")
        self.info_logger.info("📊 FINAL STATE")
        self.info_logger.info("-" * 30)
        self.info_logger.info(f"⚖️  Balance: {balance.balance:+.2f} kW {'(SURPLUS)' if balance.has_surplus else '(DEFICIT)' if balance.has_deficit else '(BALANCED)'}")
        self.info_logger.info(f"📈 Supply:  {balance.total_supply:.2f} kW")
        self.info_logger.info(f"📉 Demand:  {balance.total_demand:.2f} kW")
        
        # BESS tylko jeśli aktywny
        if self.microgrid.bess and self.microgrid.bess.actual_output != 0:
            bess = self.microgrid.bess
            charge_percent = ((bess.charge_level - bess.min_charge_level) / (bess.max_charge_level - bess.min_charge_level)) * 100
            self.info_logger.info(f"🔋 BESS: {bess.charge_level:.1f}/{bess.max_charge_level:.1f} kWh ({charge_percent:.0f}%) | {bess.actual_output:+.1f} kW")
        
        # Grid tylko jeśli aktywny
        if self.osd.actual_grid_import > 0 or self.osd.actual_grid_export > 0:
            self.info_logger.info(f"🌐 GRID: Import={self.osd.actual_grid_import:.1f} kW, Export={self.osd.actual_grid_export:.1f} kW")

    def simulate_device_state_for_calculations(self, device, operation: str, value: float):
        """
        Symuluje zmianę stanu urządzenia TYLKO dla obliczeń w bieżącej iteracji.
        
        ⚠️  WAŻNE: To NIE jest wysyłane do API/SCADA!
        
        Args:
            device: Urządzenie (BESS lub OSD)
            operation: Rodzaj operacji
            value: Nowa wartość
        """
        device_type = type(device).__name__
        
        self.info_logger.debug(
            f"🧪 SIMULATING state for {device_type}: {operation} → {value}"
        )
        
        # Symulacja dla BESS
        if device_type == "BESS":
            if operation in ["stop_charging", "stop_discharging"]:
                device.actual_output = value  # ← SYMULACJA
                self.info_logger.debug(
                    f"   → BESS.actual_output = {value} kW (simulated)"
                )
        
        # ✅ NOWE: Symulacja dla OSD
        elif device_type == "OSD":
            if operation == "stop_export":
                device.actual_grid_export = value  # ← SYMULACJA
                self.info_logger.debug(
                    f"   → OSD.actual_grid_export = {value} kW (simulated)"
                )
            elif operation == "stop_import":
                device.actual_grid_import = value  # ← SYMULACJA
                self.info_logger.debug(
                    f"   → OSD.actual_grid_import = {value} kW (simulated)"
                )
        
        self.info_logger.debug(
            f"   ℹ️  This is IN-MEMORY ONLY, will be overwritten in next iteration"
        )
    

    # =========================================================================
    # ETAP 2: PRZYWRACANIE POPRZEDNICH OGRANICZEŃ
    # =========================================================================
    
    def restore_previous_limitations(self, balance: EnergyBalance) -> EnergyBalance:
        """
        Cofa wcześniej nałożone sztucznie ograniczenia ORAZ
        sprawdza czy obecne urządzenia są ograniczone.
        
        ETAP 2: Przed zarządzaniem deficytem/nadwyżką:
        1. Cofamy poprzednie ograniczenia (z self.artificial_limitations)
        2. Sprawdzamy czy obecne urządzenia mogą pomóc
        
        Args:
            balance: Obecny bilans energetyczny
            
        Returns:
            EnergyBalance: Zaktualizowany bilans po przywróceniu
        """
        self.info_logger.info("")
        self.info_logger.info("🔄 RESTORING/CHECKING LIMITATIONS")
        self.info_logger.info("-" * 70)
        
        restored = False
        restored_count = 0
        
        # ═══════════════════════════════════════════════════════════════
        # CZĘŚĆ 1: Przywróć poprzednie ograniczenia (z artificial_limitations)
        # ═══════════════════════════════════════════════════════════════
        
        if self.artificial_limitations:
            self.info_logger.info(f"Found {len(self.artificial_limitations)} previous limitations to restore")
            
            # Dla DEFICYTU: Przywróć ograniczone generatory
            if balance.has_deficit:
                for limitation in self.artificial_limitations[:]:
                    if limitation["type"] == "generation_limit":
                        device = limitation["device"]
                        original_output = limitation["original_output"]
                        current_output = device.actual_output
                        
                        if current_output < original_output:
                            self.info_logger.info(
                                f"⚙️  Restoring {device.name}: "
                                f"{current_output:.2f} kW → {original_output:.2f} kW"
                            )
                            
                            device.setpoint_output = original_output
                            
                            device_change = {
                                "device": device,
                                "action": f"restore_output",
                                "previous_value": current_output,
                                "new_value": original_output,
                                "device_type": type(device).__name__
                            }
                            self.changed_devices.append(device_change)
                            self.artificial_limitations.remove(limitation)
                            
                            restored = True
                            restored_count += 1
            
            # Dla NADWYŻKI: Przywróć ograniczone odbiorniki
            elif balance.has_surplus:
                for limitation in self.artificial_limitations[:]:
                    if limitation["type"] == "consumption_limit":
                        device = limitation["device"]
                        original_power = limitation["original_power"]
                        was_active = limitation.get("was_active", True)
                        current_power = device.power
                        
                        if not device.switch_status and was_active:
                            self.info_logger.info(
                                f"⚙️  Restoring {device.name}: OFF → ON ({original_power:.2f} kW)"
                            )
                            
                            device.switch_status = True
                            if hasattr(device, "set_power"):
                                device.set_power(original_power)
                            else:
                                device.power = original_power
                            
                            device_change = {
                                "device": device,
                                "action": f"restore_consumer",
                                "previous_value": 0,
                                "new_value": original_power,
                                "device_type": type(device).__name__
                            }
                            self.changed_devices.append(device_change)
                            self.artificial_limitations.remove(limitation)
                            
                            restored = True
                            restored_count += 1
                        
                        elif current_power < original_power:
                            self.info_logger.info(
                                f"⚙️  Restoring {device.name}: "
                                f"{current_power:.2f} kW → {original_power:.2f} kW"
                            )
                            
                            if hasattr(device, "set_power"):
                                device.set_power(original_power)
                            else:
                                device.power = original_power
                            
                            device_change = {
                                "device": device,
                                "action": f"restore_power",
                                "previous_value": current_power,
                                "new_value": original_power,
                                "device_type": type(device).__name__
                            }
                            self.changed_devices.append(device_change)
                            self.artificial_limitations.remove(limitation)
                            
                            restored = True
                            restored_count += 1
        
        # ═══════════════════════════════════════════════════════════════
        # CZĘŚĆ 2: Sprawdź OBECNE urządzenia (nie w artificial_limitations)
        # ═══════════════════════════════════════════════════════════════
        
        # Dla DEFICYTU: Zwiększ generację
        if balance.has_deficit and not restored:
            self.info_logger.info("Checking for limited generators (not in artificial_limitations)...")
            
            # Sprawdź wszystkie generatory
            all_generators = (
                self.microgrid.pv_panels +
                self.microgrid.wind_turbines +
                self.microgrid.fuel_turbines +
                self.microgrid.fuel_cells
            )
            
            for generator in all_generators:
                if not generator.switch_status or generator.device_status != "operational":
                    continue
                
                # Czy generator ma rezerwę?
                available_increase = generator.max_output - generator.actual_output
                
                if available_increase > 0.1:  # Minimalny threshold
                    increase = min(balance.deficit, available_increase)
                    
                    self.info_logger.info(
                        f"⚙️  Increasing {generator.name}: "
                        f"{generator.actual_output:.2f} → {generator.actual_output + increase:.2f} kW "
                        f"(+{increase:.2f} kW)"
                    )
                    
                    new_output = generator.actual_output + increase
                    generator.setpoint_output = new_output
                    
                    device_change = {
                        "device": generator,
                        "action": f"increase_generation",
                        "previous_value": generator.actual_output,
                        "new_value": new_output,
                        "device_type": type(generator).__name__
                    }
                    self.changed_devices.append(device_change)
                    
                    restored = True
                    restored_count += 1
                    break  # Zwiększ tylko jeden generator na raz
        
        # Dla NADWYŻKI: Zwiększ obciążenie
        # Dla NADWYŻKI: Zwiększ obciążenie
        elif balance.has_surplus and not restored:
            self.info_logger.info("Checking for limited consumers (not in artificial_limitations)...")
            self.info_logger.info(
                f"   Found {len(self.consumergrid.adjustable_devices)} adjustable device(s)"
            )
            
            # Sprawdź adjustable devices
            for device in self.consumergrid.adjustable_devices:
                self.info_logger.info(
                    f"   🔍 Checking: {device.name} - "
                    f"switch_status={device.switch_status}, "
                    f"power={device.power:.2f}/{device.max_power:.2f} kW"
                )
                
                # Czy device OFF? Włącz go
                if not device.switch_status:
                    power_to_set = min(balance.surplus, device.max_power)
                    
                    self.info_logger.info(
                        f"⚙️  Activating {device.name}: OFF → ON ({power_to_set:.2f} kW)"
                    )
                    
                    device.switch_status = True
                    
                    if hasattr(device, "set_power"):
                        device.set_power(power_to_set)
                    else:
                        device.power = power_to_set
                    
                    device_change = {
                        "device": device,
                        "action": f"activate_consumer",
                        "previous_value": 0,
                        "new_value": power_to_set,
                        "device_type": type(device).__name__
                    }
                    self.changed_devices.append(device_change)
                    
                    restored = True
                    restored_count += 1
                    break
                
                # Czy device ma rezerwę? Zwiększ moc
                elif device.power < device.max_power:
                    available_increase = device.max_power - device.power
                    
                    self.info_logger.info(
                        f"   🔍 Available increase: {available_increase:.2f} kW"
                    )
                    
                    if available_increase > 0.1:  # Minimalny threshold
                        increase = min(balance.surplus, available_increase)
                        
                        # Zapisz wartości
                        previous_power = device.power
                        new_power = device.power + increase
                        
                        self.info_logger.info(
                            f"⚙️  Increasing {device.name}: "
                            f"{previous_power:.2f} → {new_power:.2f} kW "
                            f"(+{increase:.2f} kW)"
                        )
                        
                        # Ustaw nową moc
                        if hasattr(device, "set_power"):
                            device.set_power(new_power)
                        else:
                            device.power = new_power
                        
                        device_change = {
                            "device": device,
                            "action": f"increase_consumption",
                            "previous_value": previous_power,
                            "new_value": new_power,
                            "device_type": type(device).__name__
                        }
                        self.changed_devices.append(device_change)
                        
                        restored = True
                        restored_count += 1
                        break  # Zwiększ tylko jeden device na raz
                    else:
                        self.info_logger.info(
                            f"   ⚠️  {device.name}: available increase too small ({available_increase:.2f} kW)"
                        )
                else:
                    self.info_logger.info(
                        f"   ⚠️  {device.name}: already at max power"
                    )
        
        # ═══════════════════════════════════════════════════════════════
        # FINALIZACJA
        # ═══════════════════════════════════════════════════════════════
        
        if restored:
            self.info_logger.info(
                f"✓ Restored/increased {restored_count} device(s), recalculating balance..."
            )
            new_balance = self.calculate_energy_balance()
            self.info_logger.info(
                f"   New balance: {new_balance.balance:+.2f} kW "
                f"(was: {balance.balance:+.2f} kW, delta: {new_balance.balance - balance.balance:+.2f} kW)"
            )
            self.info_logger.info("-" * 70)
            return new_balance
        else:
            self.info_logger.info("✓ No restorable/increasable devices found")
            self.info_logger.info("-" * 70)
            return balance
    
    def save_device_state(self, device, reason: str):
        """
        Zapisuje obecny stan urządzenia przed zmianą.
        
        ETAP 2: Tracking poprzednich stanów umożliwia późniejsze przywrócenie.
        
        Args:
            device: Urządzenie do zapisania
            reason: Powód zapisu (np. "before_limitation", "before_optimization")
        """
        device_id = device.id if hasattr(device, 'id') else id(device)
        
        state = {
            "timestamp": time.time(),
            "reason": reason,
            "device_type": type(device).__name__,
        }
        
        # Zapisz specyficzne pola w zależności od typu urządzenia
        if hasattr(device, 'actual_output'):
            state["actual_output"] = device.actual_output
        if hasattr(device, 'setpoint_output'):
            state["setpoint_output"] = device.setpoint_output
        if hasattr(device, 'switch_status'):
            state["switch_status"] = device.switch_status
        if hasattr(device, 'get_current_power'):
            state["current_power"] = device.get_current_power()
        
        self.previous_device_states[device_id] = state
        
        self.info_logger.debug(
            f"Saved state for {device.name if hasattr(device, 'name') else device_id}: "
            f"{reason}"
        )
    
    def add_artificial_limitation(self, device, limitation_type: str, **kwargs):
        """
        Dodaje ograniczenie do listy śledzonych ograniczeń.
        
        ETAP 2: Śledzenie ograniczeń pozwala je później cofnąć.
        
        Args:
            device: Urządzenie, które jest ograniczane
            limitation_type: Typ ograniczenia ("generation_limit", "consumption_limit")
            **kwargs: Dodatkowe parametry (np. original_output, original_power)
        """
        limitation = {
            "device": device,
            "type": limitation_type,
            "timestamp": time.time(),
            **kwargs
        }
        
        self.artificial_limitations.append(limitation)
        
        self.info_logger.debug(
            f"Added limitation: {limitation_type} for "
            f"{device.name if hasattr(device, 'name') else 'unknown'}"
        )