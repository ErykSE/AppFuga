from apps.backend.managment.micro_grid_class import Microgrid
from apps.backend.managment.consumer_grid_class import EnergyConsumerGrid
from apps.backend.managment.energy_manager_class import EnergyManager
from apps.backend.others.osd_class import OSD
import time


if __name__ == "__main__":

    # device data
    database_file_path = "C:/eryk/AppFuga/apps/backend/initial_data.json"
    # tariff data
    tariffs_file_path = "C:/eryk/AppFuga/apps/backend/tarrif_data.json"
    # contract data
    contract_file_path = "C:/eryk/AppFuga/apps/backend/contract_data.json"

    microgrid = Microgrid()
    microgrid.load_data_from_json(database_file_path)

    print(f"Total power generated: {microgrid.total_power_generated()} kW")

    consumergrid = EnergyConsumerGrid()
    consumergrid.load_data_from_json(database_file_path)

    print(f"Total power demand: {consumergrid.total_power_consumed()} kW")

    osd = OSD.load_data_from_json(contract_file_path, tariffs_file_path)

    # Inicjalizacja i uruchomienie EnergyManager
    energy_manager = EnergyManager(microgrid, consumergrid, osd)

    try:
        energy_manager.start()  # To uruchomi wątek z run_energy_management

        # Główna pętla programu
        while True:
            time.sleep(1)  # Aby uniknąć zbyt intensywnego użycia CPU
    except KeyboardInterrupt:
        print("Zatrzymywanie aplikacji...")
        energy_manager.stop()  # To zatrzyma wątek
        print("Aplikacja zatrzymana.")
