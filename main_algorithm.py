from apps.backend.managment.micro_grid_class import Microgrid
from apps.backend.managment.consumer_grid_class import EnergyConsumerGrid
from apps.backend.managment.energy_manager_class import EnergyManager
from apps.backend.others.osd_class import OSD
from apps.backend.others.logger_config import get_loggers
import time

if __name__ == "__main__":
    # Ścieżki do plików danych
    initial_data_path = "C:/eryk/AppFuga/apps/backend/initial_data.json"
    initial_contract_path = "C:/eryk/AppFuga/apps/backend/contract_data.json"

    # Konfiguracja loggerów
    info_logger, error_logger = get_loggers()

    try:
        # Inicjalizacja mikrosieci
        microgrid = Microgrid(info_logger, error_logger)
        # microgrid.load_data_from_json(initial_data_path)

        # Inicjalizacja sieci konsumentów
        consumergrid = EnergyConsumerGrid()
        # consumergrid.load_data_from_json(initial_data_path)

        # Inicjalizacja OSD
        osd = OSD.load_data_from_json(initial_contract_path)
        if osd is None:
            raise ValueError("Failed to load OSD data from initial contract file.")

        # Inicjalizacja i uruchomienie EnergyManager
        energy_manager = EnergyManager(
            microgrid, consumergrid, osd, info_logger, error_logger
        )

        # Uruchomienie zarządzania energią
        energy_manager.start()

        # Główna pętla programu
        while True:
            time.sleep(1)  # Aby uniknąć zbyt intensywnego użycia CPU

    except KeyboardInterrupt:
        print("Zatrzymywanie aplikacji...")
        if "energy_manager" in locals():
            energy_manager.stop()  # Zatrzymanie wątku zarządzania energią
        print("Aplikacja zatrzymana.")
    except Exception as e:
        error_logger.error(f"Wystąpił błąd podczas inicjalizacji: {str(e)}")
        print(f"Wystąpił błąd: {str(e)}")
