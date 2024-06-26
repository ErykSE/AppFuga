from apps.backend.devices.pv_class import PV
from apps.backend.devices.wind_turbine_class import WindTurbine
from apps.backend.devices.fuel_turbine_class import FuelTurbine
from apps.backend.devices.fuel_cell_class import FuelCell
from apps.backend.devices.bess_class import BESS

import json


class Microgrid:
    def __init__(self):
        self.pv_panels = []
        self.wind_turbines = []
        self.fuel_turbines = []
        self.fuel_cells = []
        self.bess_units = []

    def add_device(self, device, device_type):
        if device_type == "pv_panel":
            if device.is_valid:
                self.pv_panels.append(device)
            else:
                print(f"Invalid PV Panel: {device.name}")
        elif device_type == "wind_turbine":
            if device.is_valid:
                self.wind_turbines.append(device)
            else:
                print(f"Invalid Wind Turbine: {device.name}")
        elif device_type == "fuel_turbine":
            if device.is_valid:
                self.fuel_turbines.append(device)
            else:
                print(f"Invalid Fuel Turbine: {device.name}")
        elif device_type == "fuel_cell":
            if device.is_valid:
                self.fuel_cells.append(device)
            else:
                print(f"Invalid Fuel Cell: {device.name}")
        elif device_type == "bess":
            if device.is_valid:
                self.bess_units.append(device)
            else:
                print(f"Invalid BESS: {device.name}")
        else:
            print(f"Unknown device type: {device_type}")

    def update_device(self, device_data, device_type):
        for device in getattr(self, f"{device_type}s"):
            if device.id == device_data["id"]:
                for key, value in device_data.items():
                    setattr(device, key, value)
                print(f"{device.name} updated successfully.")
                return
        new_device = self.create_device_instance(device_data, device_type)
        self.add_device(new_device, device_type)

    def create_device_instance(self, device_data, device_type):
        if device_type == "pv_panel":
            return PV.create_instance(device_data)
        elif device_type == "wind_turbine":
            return WindTurbine.create_instance(device_data)
        elif device_type == "fuel_turbine":
            return FuelTurbine.create_instance(device_data)
        elif device_type == "fuel_cell":
            return FuelCell.create_instance(device_data)
        elif device_type == "bess":
            return BESS.create_instance(device_data)
        else:
            print(f"Unknown device type: {device_type}")
            return None

    def total_power_generated(self):
        total_power = 0
        test = []
        for device_list in [
            self.pv_panels,
            self.wind_turbines,
            self.fuel_turbines,
            self.fuel_cells,
        ]:
            total_power += sum(device.get_actual_output() for device in device_list)
            test += (device.get_name() for device in device_list)
        return total_power, test

    def load_data_from_json(self, file_path):
        with open(file_path, "r") as file:
            data = json.load(file)
        for device_type in [
            "pv_panel",
            "wind_turbine",
            "fuel_turbine",
            "fuel_cell",
            "bess",
        ]:
            for device_data in data.get(f"{device_type}s", []):
                self.update_device(device_data, device_type)
