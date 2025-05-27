import requests
import urllib3
import json
import os
import time
from urllib3.exceptions import InsecureRequestWarning
from dataclasses import dataclass
from typing import Optional, Dict, Any, List

@dataclass
class RetryConfig:
    """Konfiguracja mechanizmów retry i timeoutów"""
    max_retries: int = 3
    initial_retry_delay: int = 30  # początkowe opóźnienie w sekundach
    max_retry_delay: int = 300     # maksymalne opóźnienie (5 minut)
    scada_check_interval: int = 60  # sekundy co ile sprawdzać połączenie z SCADA
    connection_timeout: int = 15    # timeout dla requestów
    max_consecutive_failures: int = 5  # po ilu kolejnych awariach przejść w tryb alarmowy
    use_exponential_backoff: bool = True  # czy używać exponential backoff

@dataclass
class SystemStatus:
    """Status systemu SCADA"""
    scada_connected: bool
    code: str
    message: str
    missing_devices: List[int]
    timestamp: str

class ApiManager:
    """
    Rozszerzona klasa zarządzająca komunikacją z API z obsługą statusu i retry logic.
    """
    
    def __init__(
        self, 
        api_base_url, 
        info_logger, 
        error_logger, 
        verify_ssl=False,
        retry_config: Optional[RetryConfig] = None
    ):
        self.api_base_url = api_base_url
        self.info_logger = info_logger
        self.error_logger = error_logger
        self.verify_ssl = verify_ssl
        self.retry_config = retry_config or RetryConfig()
        
        # Liczniki dla monitorowania
        self.consecutive_failures = 0
        self.last_successful_connection = time.time()
        self.system_in_alarm_mode = False  # zamiast zatrzymywania
        
        # Wyłączenie ostrzeżeń SSL jeśli weryfikacja jest wyłączona
        if not verify_ssl:
            urllib3.disable_warnings(InsecureRequestWarning)
        
        self.info_logger.info(f"Inicjalizacja ApiManager z bazowym URL: {api_base_url}")
        self.info_logger.info(f"Retry config: max_retries={self.retry_config.max_retries}, "
                             f"initial_delay={self.retry_config.initial_retry_delay}s, "
                             f"max_delay={self.retry_config.max_retry_delay}s, "
                             f"exponential_backoff={self.retry_config.use_exponential_backoff}, "
                             f"scada_check_interval={self.retry_config.scada_check_interval}s")
    
    def check_api_connection(self):
        """Sprawdza połączenie z API przez próbę pobrania dokumentacji Swagger."""
        url = f"{self.api_base_url}/swagger/v1/swagger.json"
        try:
            response = requests.get(url, verify=self.verify_ssl, timeout=self.retry_config.connection_timeout)
            response.raise_for_status()
            self._log_with_flag("SUCCESS", "Połączenie z API zostało nawiązane pomyślnie", "NETWORK")
            return True
        except requests.exceptions.RequestException as e:
            self._log_with_flag("ERROR", f"Błąd podczas łączenia z API: {str(e)}", "NETWORK")
            return False
        
    def _calculate_retry_delay(self, attempt: int) -> int:
        """
        Oblicza opóźnienie dla danej próby z opcjonalnym exponential backoff.
        
        Args:
            attempt: Numer próby (1, 2, 3, ...)
            
        Returns:
            int: Opóźnienie w sekundach
        """
        if not self.retry_config.use_exponential_backoff:
            return self.retry_config.initial_retry_delay
        
        # Exponential backoff: delay = initial_delay * (2 ^ (attempt - 1))
        exponential_delay = self.retry_config.initial_retry_delay * (2 ** (attempt - 1))
        
        # Ogranicz do maksymalnego opóźnienia
        actual_delay = min(exponential_delay, self.retry_config.max_retry_delay)
        
        self.info_logger.info(f"Exponential backoff: próba {attempt}, opóźnienie {actual_delay}s "
                             f"(obliczone: {exponential_delay}s, max: {self.retry_config.max_retry_delay}s) [RETRY]")
        
        return actual_delay
    
    def _log_with_flag(self, level: str, message: str, flag: str = ""):
        """
        Loguje wiadomość z odpowiednią flagą.
        
        Args:
            level: poziom loga (INFO, WARNING, ERROR, CRITICAL)
            message: treść wiadomości
            flag: dodatkowa flaga (ALERT, SYSTEM, RETRY, etc.)
        """
        flag_suffix = f" [{flag}]" if flag else ""
        formatted_message = f"{message}{flag_suffix}"
        
        if level == "CRITICAL":
            self.error_logger.critical(formatted_message)
        elif level == "ERROR":
            self.error_logger.error(formatted_message)
        elif level == "WARNING":
            self.error_logger.warning(formatted_message)
        else:
            self.info_logger.info(formatted_message)
    
    def get_system_status(self) -> Optional[SystemStatus]:
        """
        Pobiera status systemu z API.
        
        Returns:
            SystemStatus: Obiekt ze statusem systemu lub None w przypadku błędu
        """
        url = f"{self.api_base_url}/api/Scada/status"
        try:
            self.info_logger.info(f"Pobieranie statusu systemu z {url}")
            response = requests.get(url, verify=self.verify_ssl, timeout=self.retry_config.connection_timeout)
            response.raise_for_status()
            status_data = response.json()
            
            return SystemStatus(
                scada_connected=status_data.get("scadaConnected", False),
                code=status_data.get("code", "unknown"),
                message=status_data.get("message", "No message"),
                missing_devices=status_data.get("missingDevices", []),
                timestamp=status_data.get("timestamp", "")
            )
        except requests.exceptions.RequestException as e:
            self.error_logger.error(f"Błąd podczas pobierania statusu systemu: {str(e)}")
            return None

    
    def retry_system_state_connection(self, system_url: str) -> bool:
        """
        5 prób pobrania danych z /system-state z exponential backoff.
        
        Args:
            system_url: URL do endpointa system-state
            
        Returns:
            bool: True jeśli udało się pobrać dane, False w przeciwnym razie
        """
        self._log_with_flag("WARNING", "Rozpoczynam 5 prób połączenia z system-state...", "RETRY")
        
        for attempt in range(1, self.retry_config.max_consecutive_failures + 1):
            self._log_with_flag("INFO", 
                               f"Próba połączenia z system-state ({attempt}/{self.retry_config.max_consecutive_failures})", 
                               "RETRY")
            
            try:
                response = requests.get(system_url, verify=self.verify_ssl, 
                                     timeout=self.retry_config.connection_timeout)
                response.raise_for_status()
                
                # Sukces!
                self._log_with_flag("SUCCESS", "Połączenie z system-state przywrócone!", "SYSTEM")
                self.consecutive_failures = 0
                self.last_successful_connection = time.time()
                self.system_in_alarm_mode = False
                return True
                
            except requests.exceptions.RequestException as e:
                self._log_with_flag("ERROR", 
                                   f"Próba {attempt} nieudana: {str(e)}", 
                                   "RETRY")
                
                if attempt < self.retry_config.max_consecutive_failures:
                    delay = self._calculate_scada_check_delay(attempt)
                    self._log_with_flag("WARNING", 
                                       f"Następna próba za {delay} sekund...", 
                                       "RETRY")
                    time.sleep(delay)
        
        # Wszystkie próby nieudane
        self._log_with_flag("CRITICAL", 
                           f"Nie udało się połączyć z system-state po {self.retry_config.max_consecutive_failures} próbach", 
                           "ALERT")
        return False
    
    def log_final_scada_status(self):
        """
        Wykonuje GET /status dla diagnostyki i loguje wynik.
        Wywoływane po nieudanych próbach połączenia z system-state.
        """
        self._log_with_flag("INFO", "Wykonuję diagnostyczne sprawdzenie GET /status...", "SYSTEM")
        
        status_url = f"{self.api_base_url}/api/Scada/status"
        try:
            response = requests.get(status_url, verify=self.verify_ssl, 
                                timeout=self.retry_config.connection_timeout)
            response.raise_for_status()
            status_data = response.json()
            
            self._log_with_flag("INFO", f"Status SCADA - diagnostyka:", "SYSTEM")
            self._log_with_flag("INFO", f"  - scadaConnected: {status_data.get('scadaConnected', 'unknown')}", "SYSTEM")
            self._log_with_flag("INFO", f"  - code: {status_data.get('code', 'unknown')}", "SYSTEM") 
            self._log_with_flag("INFO", f"  - message: {status_data.get('message', 'unknown')}", "SYSTEM")
            self._log_with_flag("INFO", f"  - missingDevices: {status_data.get('missingDevices', [])}", "SYSTEM")
            
        except requests.exceptions.RequestException as e:
            self._log_with_flag("ERROR", f"Nie udało się pobrać statusu diagnostycznego: {str(e)}", "SYSTEM")

    def _calculate_scada_check_delay(self, attempt: int = 1) -> int:
        """Oblicza opóźnienie dla sprawdzania połączenia SCADA."""
        if not self.retry_config.use_exponential_backoff:
            return self.retry_config.scada_check_interval
        
        # Dla SCADA używamy mniejszego mnożnika (1.5 zamiast 2)
        exponential_delay = int(self.retry_config.scada_check_interval * (1.5 ** (attempt - 1)))
        return min(exponential_delay, self.retry_config.max_retry_delay)
    
    def fetch_and_save_data(self, data_path: str, contract_path: str, status_path: str) -> bool:
        """
        Pobiera dane z API i zapisuje je do plików JSON z rozdzieleniem statusu od danych urządzeń.
        
        Args:
            data_path (str): Ścieżka do pliku z danymi urządzeń
            contract_path (str): Ścieżka do pliku z danymi kontraktu
            status_path (str): Ścieżka do pliku ze statusem systemu
            
        Returns:
            bool: True jeśli operacja się powiodła, False w przeciwnym razie
        """
        try:
            # 1. Próba pobrania danych z system-state
            system_url = f"{self.api_base_url}/api/Scada/system-state"
            self.info_logger.info(f"Pobieranie danych stanu systemu z {system_url}")
            
            try:
                system_response = requests.get(system_url, verify=self.verify_ssl, 
                                             timeout=self.retry_config.connection_timeout)
                system_response.raise_for_status()
                system_data_raw = system_response.json()
                
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 503:
                    self._log_with_flag("WARNING", "API zwróciło 503 - SCADA prawdopodobnie niedostępna", "SYSTEM")
                    
                    # Zapisz status awarii do pliku
                    error_status = {
                        "code": "scada_unavailable", 
                        "message": "SCADA system unavailable (503 error)",
                        "scada_connected": False,
                        "missing_devices": [],
                        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
                    }
                    self.save_status_data(status_path, error_status)
                    
                    # 5 prób ponownego połączenia z system-state
                    if not self.retry_system_state_connection(system_url):
                        # Po nieudanych próbach - diagnostyka i zatrzymanie
                        self.log_final_scada_status()
                        
                        self.system_in_alarm_mode = True
                        self._log_with_flag("CRITICAL", 
                                           "SCADA niedostępna po wszystkich próbach - ZATRZYMANIE ALGORYTMU!", 
                                           "ALERT")
                        return False
                    
                    # Sukces po retry - pobierz dane ponownie
                    system_response = requests.get(system_url, verify=self.verify_ssl, 
                                                 timeout=self.retry_config.connection_timeout)
                    system_response.raise_for_status()
                    system_data_raw = system_response.json()
                else:
                    raise  # Inny błąd HTTP - propaguj dalej
            
            except requests.exceptions.RequestException as e:
                # Błędy połączenia (timeout, connection error itp.)
                self._log_with_flag("ERROR", f"Błąd połączenia z system-state: {str(e)}", "NETWORK")
                
                # Próby ponownego połączenia
                if not self.retry_system_state_connection(system_url):
                    self.log_final_scada_status()
                    
                    self.system_in_alarm_mode = True
                    self._log_with_flag("CRITICAL", 
                                       "Błąd połączenia po wszystkich próbach - ZATRZYMANIE ALGORYTMU!", 
                                       "ALERT")
                    return False
                
                # Sukces po retry
                system_response = requests.get(system_url, verify=self.verify_ssl, 
                                             timeout=self.retry_config.connection_timeout)
                system_response.raise_for_status()
                system_data_raw = system_response.json()
            
            # 2. Wydziel status z odpowiedzi
            status_info = system_data_raw.get("status", {})
            
            # 3. Sprawdź czy są brakujące urządzenia (pozostała logika bez zmian)
            missing_devices = status_info.get("missing_devices", [])
            if missing_devices:
                self._log_with_flag("WARNING", 
                                   f"Wykryto {len(missing_devices)} brakujących urządzeń: {missing_devices}", 
                                   "SYSTEM")
                self._log_with_flag("INFO", "Algorytm będzie kontynuowany z dostępnymi urządzeniami", "SYSTEM")
            
            # 5. Zapisz status do osobnego pliku
            self.save_status_data(status_path, status_info)
            
            # 6. Pobierz dane kontraktu
            contract_url = f"{self.api_base_url}/api/Scada/contract-info"
            self.info_logger.info(f"Pobieranie danych kontraktu z {contract_url}")
            contract_response = requests.get(contract_url, verify=self.verify_ssl, 
                                           timeout=self.retry_config.connection_timeout)
            contract_response.raise_for_status()
            contract_data = contract_response.json()
            
            # 7. Przygotuj i zapisz dane urządzeń (bez statusu)
            devices_data = self.prepare_devices_data(system_data_raw)
            contract_data_converted = self.convert_contract_data(contract_data)
            
            # 8. Zapisz pliki
            os.makedirs(os.path.dirname(data_path), exist_ok=True)
            os.makedirs(os.path.dirname(contract_path), exist_ok=True)
            
            with open(data_path, 'w', encoding='utf-8') as f:
                json.dump(devices_data, f, indent=4, ensure_ascii=False)
                
            with open(contract_path, 'w', encoding='utf-8') as f:
                json.dump(contract_data_converted, f, indent=4, ensure_ascii=False)
            
            self._log_with_flag("SUCCESS", f"Dane urządzeń zapisane do {data_path}", "SYSTEM")
            self._log_with_flag("SUCCESS", f"Dane kontraktu zapisane do {contract_path}", "SYSTEM") 
            self._log_with_flag("SUCCESS", f"Status systemu zapisany do {status_path}", "SYSTEM")
            
            # Resetuj licznik awarii po udanym pobraniu
            self.consecutive_failures = 0
            self.last_successful_connection = time.time()
            
            return True
            
        except Exception as e:
            self.consecutive_failures += 1
            self._log_with_flag("CRITICAL", 
                               f"Błąd podczas pobierania/zapisywania danych z API (awaria #{self.consecutive_failures}): {str(e)}", 
                               "ALERT")
            self.error_logger.exception("Szczegóły błędu:")
            return False
    
    def save_status_data(self, status_path: str, status_info: Dict[str, Any]):
        """Zapisuje informacje o statusie do osobnego pliku."""
        try:
            os.makedirs(os.path.dirname(status_path), exist_ok=True)
            
            # Dodaj timestamp jeśli go nie ma
            if "timestamp" not in status_info:
                status_info["timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            
            with open(status_path, 'w', encoding='utf-8') as f:
                json.dump(status_info, f, indent=4, ensure_ascii=False)
                
            self._log_with_flag("SUCCESS", f"Status zapisany: {status_info.get('message', 'Unknown status')}", "SYSTEM")
            
        except Exception as e:
            self._log_with_flag("ERROR", f"Błąd podczas zapisywania statusu: {str(e)}", "SYSTEM")
    
    def prepare_devices_data(self, system_data_raw: Dict[str, Any]) -> Dict[str, Any]:
        """Przygotowuje dane urządzeń bez informacji o statusie."""
        devices_data = {
            "pv_panels": [],
            "wind_turbines": [],
            "fuel_turbines": [],
            "fuel_cells": [],
            "bess": [],
            "non_adjustable_devices": [],
            "adjustable_devices": [],
            "power_meters": []
        }
        
        # Funkcja pomocnicza do konwersji urządzeń energetycznych
        def convert_energy_source(device, source_type):
            return {
                "id": device.get("id", 0),
                "name": device.get("name", "Unknown Device"),
                "priority": device.get("priority", 1),
                "max_output": device.get("max_output", 100),
                "min_output": device.get("min_output", 0),
                "actual_output": device.get("actual_output", 0),
                "switch_status": device.get("switch_status", False),
                "device_status": "online" if device.get("switch_status", False) else "offline"
            }
        
        # Konwersja urządzeń źródłowych
        for pv_panel in system_data_raw.get("pv_panels", []):
            devices_data["pv_panels"].append(convert_energy_source(pv_panel, "pv_panels"))
            
        for wind_turbine in system_data_raw.get("wind_turbines", []):
            devices_data["wind_turbines"].append(convert_energy_source(wind_turbine, "wind_turbines"))
            
        for fuel_turbine in system_data_raw.get("fuel_turbines", []):
            devices_data["fuel_turbines"].append(convert_energy_source(fuel_turbine, "fuel_turbines"))
            
        for fuel_cell in system_data_raw.get("fuel_cells", []):
            devices_data["fuel_cells"].append(convert_energy_source(fuel_cell, "fuel_cells"))
        
        # Konwersja BESS
        for bess in system_data_raw.get("bess", []):
            devices_data["bess"].append({
                "id": bess.get("id", 7),
                "name": bess.get("name", "BESS 1"),
                "capacity": bess.get("capacity", 350),
                "min_charge_level": bess.get("min_charge_level", 40),
                "charge_level": bess.get("charge_level", 350.0),
                "switch_status": bess.get("switch_status", True),
                "device_status": "online" if bess.get("switch_status", True) else "offline"
            })
        
        # Konwersja non-adjustable devices
        for device in system_data_raw.get("non_adjustable_devices", []):
            # Pobierz wartość mocy - może być w actual_power lub power
            power_value = 0
            if "actual_power" in device:
                power_value = device["actual_power"]
            elif "power" in device:
                power_value = device["power"]
                
            devices_data["non_adjustable_devices"].append({
                "id": device.get("id", 0),
                "name": device.get("name", "Unknown Device"),
                "priority": device.get("priority", 1),
                "power": power_value,
                "switch_status": device.get("switch_status", False)
            })
        
        # Konwersja adjustable devices
        for device in system_data_raw.get("adjustable_devices", []):
            # Pobierz wartość mocy - może być w actual_power lub power
            power_value = 0
            if "actual_power" in device:
                power_value = device["actual_power"]
            elif "power" in device:
                power_value = device["power"]
                
            devices_data["adjustable_devices"].append({
                "id": device.get("id", 0),
                "name": device.get("name", "Unknown Device"),
                "priority": device.get("priority", 1),
                "power": power_value,
                "switch_status": device.get("switch_status", False),
                "min_power": device.get("min_power", 30),
                "max_power": device.get("max_power", 100)
            })
        
        # Konwersja liczników energii (power meters)
        for meter in system_data_raw.get("power_meters", []):
            devices_data["power_meters"].append({
                "id": meter.get("id", 0),
                "name": meter.get("name", "Unknown Meter"),
                "status": meter.get("status", "online"),
                "measured_power": meter.get("measured_power", 0),
                "device_id": meter.get("device_id", 0)
            })
        
        return devices_data
    
    def convert_contract_data(self, contract_data: Dict[str, Any]) -> Dict[str, Any]:
        """Konwertuje dane kontraktu z camelCase na wymagany format."""
        return {
            "CONTRACTED_TYPE": contract_data.get("contractedType", ""),
            "CONTRACTED_DURATION": contract_data.get("contractedDuration", 0),
            "CONTRACTED_MARGIN": contract_data.get("contractedMargin", 0),
            "CONTRACTED_EXPORT_POSSIBILITY": contract_data.get("contractedExportPossibility", False),
            "CONTRACTED_SALE_LIMIT": contract_data.get("contractedSaleLimit", 0),
            "CONTRACTED_PURCHASE_LIMIT": contract_data.get("contractedPurchaseLimit", 0),
            "sold_power": contract_data.get("soldPower", 0),
            "bought_power": contract_data.get("boughtPower", 0),
            "current_tariff_buy": contract_data.get("currentTariffBuy", 0),
            "current_tariff_sell": contract_data.get("currentTariffSell", 0)
        }
    
    def send_updated_data_with_retry(self, system_data: Dict[str, Any], contract_data: Dict[str, Any]) -> bool:
        """
        Wysyła dane do API z mechanizmem retry.
        
        Args:
            system_data: Dane systemu do wysłania
            contract_data: Dane kontraktu do wysłania
            
        Returns:
            bool: True jeśli udało się wysłać, False w przeciwnym razie
        """
        # Próba wysłania danych systemu
        if not self._send_system_data_with_retry(system_data):
            return False
        
        # Próba wysłania danych kontraktu
        if not self._send_contract_data_with_retry(contract_data):
            return False
        
        return True
    
    def _send_system_data_with_retry(self, system_data: Dict[str, Any]) -> bool:
        """Wysyła dane systemu z mechanizmem retry i exponential backoff."""
        url = f"{self.api_base_url}/api/Scada/update-system-state"
        headers = {"Content-Type": "application/json"}
        
        for attempt in range(1, self.retry_config.max_retries + 1):
            try:
                self._log_with_flag("INFO", 
                                   f"Wysyłanie danych systemu (próba {attempt}/{self.retry_config.max_retries})", 
                                   "RETRY")
                
                response = requests.post(
                    url,
                    json=system_data,
                    headers=headers,
                    verify=self.verify_ssl,
                    timeout=self.retry_config.connection_timeout
                )
                response.raise_for_status()
                
                # Sprawdź odpowiedź z API
                response_data = response.json()
                if response_data.get("success", False):
                    self._log_with_flag("SUCCESS", "Dane systemu wysłane pomyślnie", "NETWORK")
                    return True
                else:
                    error_msg = response_data.get('message', 'Unknown error')
                    self._log_with_flag("WARNING", f"API zwróciło błąd: {error_msg}", "RETRY")
                    
                    if attempt < self.retry_config.max_retries:
                        delay = self._calculate_retry_delay(attempt)
                        self._log_with_flag("INFO", f"Ponowna próba za {delay} sekund...", "RETRY")
                        time.sleep(delay)
                    continue
                    
            except requests.exceptions.RequestException as e:
                self._log_with_flag("ERROR", 
                                   f"Błąd podczas wysyłania danych systemu (próba {attempt}): {str(e)}", 
                                   "RETRY")
                
                if attempt < self.retry_config.max_retries:
                    delay = self._calculate_retry_delay(attempt)
                    self._log_with_flag("INFO", f"Ponowna próba za {delay} sekund...", "RETRY")
                    time.sleep(delay)
                else:
                    self._log_with_flag("CRITICAL", 
                                       "Przekroczono maksymalną liczbę prób wysłania danych systemu", 
                                       "ALERT")
        
        return False
    
    def _send_contract_data_with_retry(self, contract_data: Dict[str, Any]) -> bool:
        """Wysyła dane kontraktu z mechanizmem retry i exponential backoff."""
        url = f"{self.api_base_url}/api/Scada/update-contract"
        headers = {"Content-Type": "application/json"}
        
        for attempt in range(1, self.retry_config.max_retries + 1):
            try:
                self._log_with_flag("INFO", 
                                   f"Wysyłanie danych kontraktu (próba {attempt}/{self.retry_config.max_retries})", 
                                   "RETRY")
                
                response = requests.post(
                    url,
                    json=contract_data,
                    headers=headers,
                    verify=self.verify_ssl,
                    timeout=self.retry_config.connection_timeout
                )
                response.raise_for_status()
                
                # Sprawdź odpowiedź z API
                response_data = response.json()
                if "Message" in response_data and "successfully" in response_data["Message"]:
                    self._log_with_flag("SUCCESS", "Dane kontraktu wysłane pomyślnie", "NETWORK")
                    return True
                else:
                    self._log_with_flag("WARNING", f"Nieoczekiwana odpowiedź API: {response_data}", "RETRY")
                    
                    if attempt < self.retry_config.max_retries:
                        delay = self._calculate_retry_delay(attempt)
                        self._log_with_flag("INFO", f"Ponowna próba za {delay} sekund...", "RETRY")
                        time.sleep(delay)
                    continue
                    
            except requests.exceptions.RequestException as e:
                self._log_with_flag("ERROR", 
                                   f"Błąd podczas wysyłania danych kontraktu (próba {attempt}): {str(e)}", 
                                   "RETRY")
                
                if attempt < self.retry_config.max_retries:
                    delay = self._calculate_retry_delay(attempt)
                    self._log_with_flag("INFO", f"Ponowna próba za {delay} sekund...", "RETRY")
                    time.sleep(delay)
                else:
                    self._log_with_flag("CRITICAL", 
                                       "Przekroczono maksymalną liczbę prób wysłania danych kontraktu", 
                                       "ALERT")
        
        return False
    
    # Metoda pomocnicza do przygotowania urządzenia do wysyłki do API
    def _prepare_device_for_api(self, device, category):
        """
        Przygotowuje urządzenie do wysyłki do API.
        
        Args:
            device (dict): Słownik zawierający dane urządzenia.
            category (str): Kategoria urządzenia.
            
        Returns:
            dict: Słownik zawierający dane urządzenia w formacie API.
        """
        if category in ["pv_panels", "wind_turbines", "fuel_turbines", "fuel_cells"]:
            return {
                "name": device.get("name", ""),
                "actual_output": device.get("actual_output", 0),
                "switch_status": device.get("switch_status", False)
            }
        elif category == "bess":
            return {
                "name": device.get("name", ""),
                "actual_output": 0,  # BESS nie ma actual_output w API
                "switch_status": device.get("switch_status", False)
            }
        elif category in ["non_adjustable_devices", "adjustable_devices"]:
            return {
                "name": device.get("name", ""),
                "actual_output": device.get("power", 0),  # Mapowanie power na actual_output
                "switch_status": device.get("switch_status", False)
            }
        else:
            return {}
    
    def send_updated_data(self, original_data_path, modified_data_path, original_contract_path, modified_contract_path):
        """
        Porównuje oryginalne dane z zmodyfikowanymi i wysyła tylko zmienione urządzenia do API.
        
        Args:
            original_data_path (str): Ścieżka do pliku z oryginalnymi danymi systemu.
            modified_data_path (str): Ścieżka do pliku ze zmodyfikowanymi danymi systemu.
            original_contract_path (str): Ścieżka do pliku z oryginalnymi danymi kontraktu.
            modified_contract_path (str): Ścieżka do pliku ze zmodyfikowanymi danymi kontraktu.
            
        Returns:
            bool: True jeśli aktualizacja została pomyślnie wysłana, False w przeciwnym razie.
        """
        try:
            # Wczytaj oryginalne i zmodyfikowane dane
            with open(original_data_path, 'r', encoding='utf-8') as f:
                original_data = json.load(f)
                
            with open(modified_data_path, 'r', encoding='utf-8') as f:
                modified_data = json.load(f)
                
            with open(original_contract_path, 'r', encoding='utf-8') as f:
                original_contract = json.load(f)
                
            with open(modified_contract_path, 'r', encoding='utf-8') as f:
                modified_contract = json.load(f)
            
            # Przygotowanie danych do wysyłki - tylko zmienione urządzenia
            changed_devices_data = {
                "pv_panels": [],
                "wind_turbines": [],
                "fuel_turbines": [],
                "fuel_cells": [],
                "bess": [],
                "non_adjustable_devices": [],
                "adjustable_devices": [],
                "power_meters": []
            }
            
            # Funkcja do wykrywania zmian w urządzeniach
            def detect_changes(original_list, modified_list, category):
                changed_devices = []
                
                # Stwórz słownik ID -> urządzenie dla łatwiejszego wyszukiwania
                original_dict = {str(device.get("id", "")): device for device in original_list}
                
                for device in modified_list:
                    device_id = str(device.get("id", ""))
                    
                    # Jeśli urządzenie istnieje w oryginalnych danych, sprawdź czy się zmieniło
                    if device_id in original_dict:
                        original_device = original_dict[device_id]
                        
                        # W zależności od kategorii, porównuj różne pola
                        if category in ["pv_panels", "wind_turbines", "fuel_turbines", "fuel_cells"]:
                            if (device.get("actual_output", 0) != original_device.get("actual_output", 0) or
                                device.get("switch_status", False) != original_device.get("switch_status", False) or
                                device.get("device_status", "") != original_device.get("device_status", "")):
                                changed_devices.append(self._prepare_device_for_api(device, category))
                        
                        elif category == "bess":
                            if (device.get("charge_level", 0) != original_device.get("charge_level", 0) or
                                device.get("switch_status", False) != original_device.get("switch_status", False) or
                                device.get("device_status", "") != original_device.get("device_status", "")):
                                changed_devices.append(self._prepare_device_for_api(device, category))
                        
                        elif category in ["non_adjustable_devices", "adjustable_devices"]:
                            if (device.get("power", 0) != original_device.get("power", 0) or
                                device.get("switch_status", False) != original_device.get("switch_status", False)):
                                changed_devices.append(self._prepare_device_for_api(device, category))
                    else:
                        # Nowe urządzenie, dodaj je do zmian
                        changed_devices.append(self._prepare_device_for_api(device, category))
                
                return changed_devices
            
            # Wykrywanie zmian dla każdej kategorii urządzeń
            for category in ["pv_panels", "wind_turbines", "fuel_turbines", "fuel_cells", "bess", 
                            "non_adjustable_devices", "adjustable_devices"]:
                changed_devices_data[category] = detect_changes(
                    original_data.get(category, []), 
                    modified_data.get(category, []),
                    category
                )
            
            # Sprawdź czy są jakiekolwiek zmiany w urządzeniach
            changes_detected = any(len(devices) > 0 for devices in changed_devices_data.values())
            
            if changes_detected:
                self.info_logger.info("Wykryto zmiany w urządzeniach. Wysyłanie aktualizacji do API.")
                
                # Wysyłamy tylko zmienione urządzenia z retry
                if not self._send_system_data_with_retry(changed_devices_data):
                    self._log_with_flag("ERROR", "Nie udało się wysłać danych systemu po wszystkich próbach", "ALERT")
                    return False
            else:
                self.info_logger.info("Nie wykryto zmian w urządzeniach. Pomijanie wysyłania aktualizacji.")
            
            # Sprawdź czy są zmiany w kontrakcie
            contract_changes = False
            for key in ["sold_power", "bought_power"]:
                if modified_contract.get(key, 0) != original_contract.get(key, 0):
                    contract_changes = True
                    break
            
            if contract_changes:
                self.info_logger.info("Wykryto zmiany w kontrakcie. Wysyłanie aktualizacji do API.")
                
                # Przygotowanie danych kontraktu w formacie API
                api_contract_data = {
                    "contracted_type": modified_contract.get("CONTRACTED_TYPE", ""),
                    "contracted_duration": modified_contract.get("CONTRACTED_DURATION", 0),
                    "contracted_margin": modified_contract.get("CONTRACTED_MARGIN", 0),
                    "contracted_export_possibility": modified_contract.get("CONTRACTED_EXPORT_POSSIBILITY", False),
                    "contracted_sale_limit": modified_contract.get("CONTRACTED_SALE_LIMIT", 0),
                    "contracted_purchase_limit": modified_contract.get("CONTRACTED_PURCHASE_LIMIT", 0),
                    "sold_power": modified_contract.get("sold_power", 0),
                    "bought_power": modified_contract.get("bought_power", 0),
                    "current_tariff_buy": modified_contract.get("current_tariff_buy", 0),
                    "current_tariff_sell": modified_contract.get("current_tariff_sell", 0)
                }
                
                # Wysyłamy zaktualizowane dane kontraktu z retry
                if not self._send_contract_data_with_retry(api_contract_data):
                    self._log_with_flag("ERROR", "Nie udało się wysłać danych kontraktu po wszystkich próbach", "ALERT")
                    return False
            else:
                self.info_logger.info("Nie wykryto zmian w kontrakcie. Pomijanie wysyłania aktualizacji.")
            
            return True
        except Exception as e:
            self._log_with_flag("CRITICAL", f"Błąd podczas wysyłania aktualizacji do API: {str(e)}", "ALERT")
            self.error_logger.exception("Szczegóły błędu:")
            return False