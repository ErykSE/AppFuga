from apps.backend.managment.micro_grid_class import Microgrid
from apps.backend.managment.consumer_grid_class import EnergyConsumerGrid
from apps.backend.managment.energy_manager_class import EnergyManager
from apps.backend.others.osd_class import OSD
from apps.backend.others.logger_config import get_loggers
import time


if __name__ == "__main__":
    # device data
    database_file_path = "C:/eryk/AppFuga/apps/backend/initial_data.json"

    # contract data
    contract_file_path = "C:/eryk/AppFuga/apps/backend/contract_data.json"

    info_logger, error_logger = get_loggers()

    microgrid = Microgrid()
    microgrid.load_data_from_json(database_file_path)

    consumergrid = EnergyConsumerGrid()
    consumergrid.load_data_from_json(database_file_path)

    osd = OSD.load_data_from_json(contract_file_path)

    # Inicjalizacja i uruchomienie EnergyManager
    # energy_manager = EnergyManager(microgrid, consumergrid, osd)
    energy_manager = EnergyManager(
        microgrid, consumergrid, osd, info_logger, error_logger
    )

    try:
        energy_manager.start()  # To uruchomi wątek z run_energy_management

        # Główna pętla programu
        while True:
            time.sleep(1)  # Aby uniknąć zbyt intensywnego użycia CPU
    except KeyboardInterrupt:
        print("Zatrzymywanie aplikacji...")
        energy_manager.stop()  # To zatrzyma wątek
        print("Aplikacja zatrzymana.")
