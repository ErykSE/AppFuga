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
        self.bess = []  # Zmieniono nazwę na bess_units dla spójności

    def add_device(self, device, device_type):
        if device_type == "bess":
            device_list = self.bess
        else:
            device_list = getattr(self, f"{device_type}s")

        if device.is_valid:
            device_list.append(device)
            print(f"Added {device_type}: {device.name}")
        else:
            print(f"Invalid {device_type}: {device.name}")

    def update_device(self, device_data, device_type):
        print(f"Attempting to update {device_type}: {device_data}")
        if device_type == "bess":
            device_list = self.bess
        else:
            device_list = getattr(self, f"{device_type}s")

        for device in device_list:
            if device.id == device_data["id"]:
                for key, value in device_data.items():
                    setattr(device, key, value)
                print(f"{device_type.capitalize()} {device.name} updated successfully.")
                return
        # Jeśli urządzenie nie istnieje, tworzymy nowe
        new_device = self.create_device_instance(device_data, device_type)
        if new_device:
            self.add_device(new_device, device_type)
        else:
            print(f"Failed to create new {device_type} device")

    def create_device_instance(self, device_data, device_type):
        # Ta metoda tworzy instancję odpowiedniego urządzenia
        device_classes = {
            "pv_panel": PV,
            "wind_turbine": WindTurbine,
            "fuel_turbine": FuelTurbine,
            "fuel_cell": FuelCell,
            "bess": BESS,
        }
        device_class = device_classes.get(device_type)
        if device_class:
            return device_class.create_instance(device_data)
        else:
            print(f"Unknown device type: {device_type}")
            return None

    def total_power_generated(self):
        # Ta metoda oblicza całkowitą wygenerowaną moc
        return sum(
            device.get_actual_output()
            for device_list in [
                self.pv_panels,
                self.wind_turbines,
                self.fuel_turbines,
                self.fuel_cells,
            ]
            for device in device_list
        )

    def get_all_devices(self):
        # Ta metoda zwraca listę wszystkich urządzeń
        return (
            self.pv_panels
            + self.wind_turbines
            + self.fuel_turbines
            + self.fuel_cells
            + self.bess
        )

    def get_active_devices(self):
        # Ta metoda zwraca listę aktywnych urządzeń
        return [
            device
            for device in self.get_all_devices()
            if device.get_status() == "online"
        ]

    def get_inactive_devices(self):
        # Ta metoda zwraca listę nieaktywnych urządzeń
        return [
            device
            for device in self.get_all_devices()
            if device.get_status() == "offline"
        ]

    def load_data_from_json(self, file_path):
        with open(file_path, "r") as file:
            data = json.load(file)
        print(f"Loaded data from JSON: {data}")
        device_types = {
            "pv_panels": "pv_panel",
            "wind_turbines": "wind_turbine",
            "fuel_turbines": "fuel_turbine",
            "fuel_cells": "fuel_cell",
            "bess": "bess",  # Bez zmiany
        }
        for json_key, device_type in device_types.items():
            devices = data.get(json_key, [])
            print(f"Processing {json_key}: {devices}")
            for device_data in devices:
                self.update_device(device_data, device_type)

        print(f"After loading, BESS units: {len(self.bess)}")
        for bess in self.bess:
            print(f"BESS: {bess.name}, ID: {bess.id}")
