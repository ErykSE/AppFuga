from apps.backend.managment.micro_grid_class import Microgrid
from apps.backend.managment.consumer_grid_class import EnergyConsumerGrid
from apps.backend.managment.energy_manager_class import EnergyManager
from apps.backend.others.osd_class import OSD
from apps.backend.others.logger_config import get_loggers

import time
import requests
import json
import urllib3

# Ścieżki do zapisu plików JSON
INITIAL_DATA_PATH = "C:/Users/Julia/desktop/Fuga/AppFuga/apps/backend/initial_data.json"
CONTRACT_DATA_PATH = "C:/Users/Julia/desktop/Fuga/AppFuga/apps/backend/contract_data.json"

# Adres API
API_BASE_URL = "https://localhost:7106"

# Wyłączenie ostrzeżeń SSL (dla lokalnych certyfikatów)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- Funkcje do pobierania danych z API ---

def get_system_state():
    url = f"{API_BASE_URL}/api/Scada/system-state"
    response = requests.get(url, verify=False)
    response.raise_for_status()
    return response.json()

def get_contract_info():
    url = f"{API_BASE_URL}/api/Scada/contract-info"
    response = requests.get(url, verify=False)
    response.raise_for_status()
    return response.json()

def save_json_to_file(data, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# --- Główna logika ---

if __name__ == "__main__":
    info_logger, error_logger = get_loggers()

    try:
        # --- 1. Pobieranie danych z API ---
        system_state = get_system_state()
        contract_info = get_contract_info()

        # --- 2. Konwersja danych z API na oczekiwany format ---

        # Konwersja system_state jeśli też potrzebuje – na razie zapisujemy surowo
        save_json_to_file(system_state, INITIAL_DATA_PATH)

        # Konwersja contract_info (camelCase → wymagany format)
        converted_contract_info = {
            "CONTRACTED_TYPE": contract_info.get("contractedType", ""),
            "CONTRACTED_DURATION": contract_info.get("contractedDuration", 0),
            "CONTRACTED_MARGIN": contract_info.get("contractedMargin", 0),
            "CONTRACTED_EXPORT_POSSIBILITY": contract_info.get("contractedExportPossibility", False),
            "CONTRACTED_SALE_LIMIT": contract_info.get("contractedSaleLimit", 0),
            "CONTRACTED_PURCHASE_LIMIT": contract_info.get("contractedPurchaseLimit", 0),
            "sold_power": contract_info.get("soldPower", 0),
            "bought_power": contract_info.get("boughtPower", 0),
            "current_tariff_buy": contract_info.get("currentTariffBuy", 0),
            "current_tariff_sell": contract_info.get("currentTariffSell", 0)
        }

        save_json_to_file(converted_contract_info, CONTRACT_DATA_PATH)

        # --- 3. Inicjalizacja klas ---
        microgrid = Microgrid(info_logger, error_logger)
        microgrid.load_data_from_json(INITIAL_DATA_PATH)

        consumergrid = EnergyConsumerGrid()
        consumergrid.load_data_from_json(INITIAL_DATA_PATH)

        osd = OSD.load_data_from_json(CONTRACT_DATA_PATH)
        if osd is None:
            raise ValueError("Nie udało się załadować danych OSD z pliku.")

        # --- 4. Start systemu zarządzania energią ---
        energy_manager = EnergyManager(microgrid, consumergrid, osd, info_logger, error_logger)
        energy_manager.start()

        # --- 5. Główna pętla ---
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("Zatrzymywanie aplikacji...")
        if "energy_manager" in locals():
            energy_manager.stop()
        print("Aplikacja zatrzymana.")

    except Exception as e:
        error_logger.error(f"Wystąpił błąd podczas inicjalizacji: {str(e)}")
        print(f"Wystąpił błąd: {str(e)}")