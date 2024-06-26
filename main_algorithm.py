from apps.backend.managment.micro_grid_class import Microgrid

# from apps.backend.managment.energy_consumer_grid_class import EnergyConsumerGrid

if __name__ == "__main__":

    # Przykład użycia
    file_path = "C:/eryk/AppFuga/apps/backend/initial_data.json"

    microgrid = Microgrid()
    microgrid.load_data_from_json(file_path)

    print(f"Total power generated: {microgrid.total_power_generated()} kW")

    # consumergrid = EnergyConsumerGrid()
    # consumergrid.load_data_from_json(file_path)

# print(f"Total power generated: {consumergrid.total_power_consumed()} kW")
