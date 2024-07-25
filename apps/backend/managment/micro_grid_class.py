from apps.backend.devices.pv_class import PV
from apps.backend.devices.wind_turbine_class import WindTurbine
from apps.backend.devices.fuel_turbine_class import FuelTurbine
from apps.backend.devices.fuel_cell_class import FuelCell
from apps.backend.devices.bess_class import BESS

import json
import os


class Microgrid:
    """
    Główna klasa zarządzająca urządzeniami generującymi moc.
    """

    def __init__(self):
        self.pv_panels = []
        self.wind_turbines = []
        self.fuel_turbines = []
        self.fuel_cells = []
        self.bess = None

    def add_device(self, device, device_type):
        if device_type == "bess":
            if self.bess is None:
                self.bess = device
                print(f"Added BESS: {device.name}")
            else:
                print("BESS already exists. Cannot add another one.")
        else:
            device_list = getattr(self, f"{device_type}s")
            if device.is_valid:
                device_list.append(device)
                print(f"Added {device_type}: {device.name}")
            else:
                print(f"Invalid {device_type}: {device.name}")

    def update_device(self, device_data, device_type):
        print(f"Attempting to update {device_type}: {device_data}")

        if not isinstance(device_data, dict):
            print(f"Error: Invalid data format for {device_type}. Expected dictionary.")
            return

        required_fields = {
            "bess": ["id", "name", "capacity", "charge_level"],
            "pv_panel": ["id", "name", "max_output", "actual_output"],
            "wind_turbine": ["id", "name", "max_output", "actual_output"],
            "fuel_turbine": ["id", "name", "max_output", "actual_output"],
            "fuel_cell": ["id", "name", "max_output", "actual_output"],
        }

        if device_type not in required_fields:
            print(f"Error: Unknown device type {device_type}")
            return

        for field in required_fields[device_type]:
            if field not in device_data:
                print(f"Error: Missing required field '{field}' for {device_type}")
                return

        if device_type == "bess":
            if self.bess and self.bess.id == device_data["id"]:
                for key, value in device_data.items():
                    if hasattr(self.bess, key):
                        setattr(self.bess, key, value)
                    else:
                        print(f"Warning: Unknown attribute '{key}' for BESS")
                print(f"BESS {self.bess.name} updated successfully.")
            elif self.bess is None:
                new_device = self.create_device_instance(device_data, device_type)
                if new_device:
                    self.bess = new_device
                    print(f"New BESS added: {new_device.name}")
                else:
                    print("Failed to create new BESS device")
            else:
                print("Cannot update BESS. ID mismatch or BESS already exists.")
        else:
            device_list = getattr(self, f"{device_type}s")
            for device in device_list:
                if device.id == device_data["id"]:
                    for key, value in device_data.items():
                        if hasattr(device, key):
                            setattr(device, key, value)
                        else:
                            print(
                                f"Warning: Unknown attribute '{key}' for {device_type}"
                            )
                    print(
                        f"{device_type.capitalize()} {device.name} updated successfully."
                    )
                    return
            # Jeśli urządzenie nie istnieje, tworzymy nowe
            new_device = self.create_device_instance(device_data, device_type)
            if new_device:
                self.add_device(new_device, device_type)
            else:
                print(f"Failed to create new {device_type} device")

    def create_device_instance(self, device_data, device_type):
        device_classes = {
            "pv_panel": PV,
            "wind_turbine": WindTurbine,
            "fuel_turbine": FuelTurbine,
            "fuel_cell": FuelCell,
            "bess": BESS,
        }
        device_class = device_classes.get(device_type)
        if device_class:
            instance = device_class.create_instance(device_data)
            if instance:
                print(f"Successfully created {device_type} instance: {instance.name}")
                return instance
            else:
                print(f"Failed to create {device_type} instance")
                return None
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
        # Ta metoda zwraca listę wszystkich urządzeń generujących moc
        return (
            self.pv_panels + self.wind_turbines + self.fuel_turbines + self.fuel_cells
        )

    def get_active_devices(self):
        active_devices = [
            device
            for device in self.get_all_devices()
            if device.get_status() == "online"
        ]
        print(f"Liczba aktywnych urządzeń: {len(active_devices)}")
        for device in active_devices:
            print(
                f"Aktywne urządzenie: {device.name}, moc: {device.get_actual_output()} kW"
            )
        return active_devices

    def get_inactive_devices(self):
        inactive_devices = [
            device
            for device in self.get_all_devices()
            if device.get_status() == "offline"
        ]
        print(f"Liczba nieaktywnych urządzeń: {len(inactive_devices)}")
        return inactive_devices

    def has_inactive_devices(self):
        return len(self.get_inactive_devices()) > 0

    def load_data_from_json(self, file_path):
        try:
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"File not found: {file_path}")

            with open(file_path, "r") as file:
                data = json.load(file)

            device_types = {
                "pv_panels": "pv_panel",
                "wind_turbines": "wind_turbine",
                "fuel_turbines": "fuel_turbine",
                "fuel_cells": "fuel_cell",
                "bess": "bess",
            }

            for json_key, device_type in device_types.items():
                devices = data.get(json_key, [])
                for device_data in devices:
                    self.update_device(device_data, device_type)

            print("Data loaded successfully.")
        except FileNotFoundError as e:
            print(f"Error: {e}")
        except json.JSONDecodeError:
            print(f"Error: Invalid JSON format in file {file_path}")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
