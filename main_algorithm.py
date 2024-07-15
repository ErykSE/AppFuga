from apps.backend.managment.micro_grid_class import Microgrid
from apps.backend.managment.consumer_grid_class import EnergyConsumerGrid
from apps.backend.managment.energy_manager_class import EnergyManager
from apps.backend.others.osd_class import OSD
from apps.backend.test.test1 import unittest

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

    energy_manager = EnergyManager(microgrid, consumergrid, osd)
    energy_manager.check_energy_conditions()

    # unittest.main()
