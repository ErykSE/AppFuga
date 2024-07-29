from apps.backend.devices.pv_class import PV
from apps.backend.devices.wind_turbine_class import WindTurbine
from apps.backend.devices.fuel_turbine_class import FuelTurbine
from apps.backend.devices.fuel_cell_class import FuelCell
from apps.backend.devices.bess_class import BESS

import json
import os


class Microgrid:
    """
    Główna klasa zarządzająca urządzeniami generującymi moc w mikrosieci.

    Klasa ta odpowiada za przechowywanie, dodawanie, aktualizację i zarządzanie
    różnymi typami urządzeń energetycznych, takimi jak panele fotowoltaiczne,
    turbiny wiatrowe, turbiny paliwowe, ogniwa paliwowe oraz system magazynowania
    energii (BESS).

    Attributes:
        pv_panels (list): Lista obiektów reprezentujących panele fotowoltaiczne.
        wind_turbines (list): Lista obiektów reprezentujących turbiny wiatrowe.
        fuel_turbines (list): Lista obiektów reprezentujących turbiny paliwowe.
        fuel_cells (list): Lista obiektów reprezentujących ogniwa paliwowe.
        bess (BESS or None): Obiekt reprezentujący system magazynowania energii (BESS).
    """

    def __init__(self, info_logger, error_logger):
        self.pv_panels = []
        self.wind_turbines = []
        self.fuel_turbines = []
        self.fuel_cells = []
        self.bess = None
        self.info_logger = info_logger
        self.error_logger = error_logger

    def add_device(self, device, device_type):
        """
        Dodaje nowe urządzenie do odpowiedniej listy w mikrosieci.

        Args:
            device (object): Obiekt reprezentujący urządzenie do dodania.
            device_type (str): Typ urządzenia ('pv_panel', 'wind_turbine', 'fuel_turbine', 'fuel_cell', 'bess').

        Notes:
            Dla BESS możliwe jest dodanie tylko jednego urządzenia.
        """
        if device_type == "bess":
            if self.bess is None:
                self.bess = device
                self.info_logger.info(f"Added BESS: {device.name}")
            else:
                self.error_logger.error("BESS already exists. Cannot add another one.")
        else:
            device_list = getattr(self, f"{device_type}s")
            if device.is_valid:
                device_list.append(device)
                self.info_logger.info(f"Added {device_type}: {device.name}")
            else:
                self.error_logger.error(f"Invalid {device_type}: {device.name}")

    def update_device(self, device_data, device_type):
        """
        Aktualizuje istniejące urządzenie lub dodaje nowe, jeśli nie istnieje.

        Args:
            device_data (dict): Słownik zawierający dane urządzenia do aktualizacji.
            device_type (str): Typ urządzenia ('pv_panel', 'wind_turbine', 'fuel_turbine', 'fuel_cell', 'bess').

        Notes:
            Metoda sprawdza, czy urządzenie o danym ID już istnieje. Jeśli tak, aktualizuje jego dane.
            Jeśli nie, tworzy nowe urządzenie i dodaje je do odpowiedniej listy.
        """
        self.info_logger.info(f"Attempting to update {device_type}: {device_data}")

        if not isinstance(device_data, dict):
            self.error_logger.error(
                f"Invalid data format for {device_type}. Expected dictionary."
            )
            return

        required_fields = {
            "bess": ["id", "name", "capacity", "charge_level"],
            "pv_panel": ["id", "name", "max_output", "actual_output"],
            "wind_turbine": ["id", "name", "max_output", "actual_output"],
            "fuel_turbine": ["id", "name", "max_output", "actual_output"],
            "fuel_cell": ["id", "name", "max_output", "actual_output"],
        }

        if device_type not in required_fields:
            self.error_logger.error(f"Unknown device type {device_type}")
            return

        for field in required_fields[device_type]:
            if field not in device_data:
                self.error_logger.error(
                    f"Missing required field '{field}' for {device_type}"
                )
                return

        if device_type == "bess":
            if self.bess and self.bess.id == device_data["id"]:
                for key, value in device_data.items():
                    if hasattr(self.bess, key):
                        setattr(self.bess, key, value)
                    else:
                        self.error_logger.warning(f"Unknown attribute '{key}' for BESS")
                self.info_logger.info(f"BESS {self.bess.name} updated successfully.")
            elif self.bess is None:
                new_device = self.create_device_instance(device_data, device_type)
                if new_device:
                    self.bess = new_device
                    self.info_logger.info(f"New BESS added: {new_device.name}")
                else:
                    self.error_logger.error("Failed to create new BESS device")
            else:
                self.error_logger.error(
                    "Cannot update BESS. ID mismatch or BESS already exists."
                )
        else:
            device_list = getattr(self, f"{device_type}s")
            for device in device_list:
                if device.id == device_data["id"]:
                    for key, value in device_data.items():
                        if hasattr(device, key):
                            setattr(device, key, value)
                        else:
                            self.error_logger.error(
                                f"Warning: Unknown attribute '{key}' for {device_type}"
                            )
                    self.info_logger.info(
                        f"{device_type.capitalize()} {device.name} updated successfully."
                    )
                    return
            # Jeśli urządzenie nie istnieje, tworzymy nowe
            new_device = self.create_device_instance(device_data, device_type)
            if new_device:
                self.add_device(new_device, device_type)
            else:
                self.error_logger.error(f"Failed to create new {device_type} device")

    def create_device_instance(self, device_data, device_type):
        """
        Tworzy nową instancję urządzenia na podstawie podanych danych.

        Args:
            device_data (dict): Słownik zawierający dane do utworzenia urządzenia.
            device_type (str): Typ urządzenia do utworzenia.

        Returns:
            object or None: Nowa instancja urządzenia lub None w przypadku niepowodzenia.
        """
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
                self.info_logger.info(
                    f"Successfully created {device_type} instance: {instance.name}"
                )
                return instance
            else:
                self.error_logger.error(f"Failed to create {device_type} instance")
                return None
        else:
            self.error_logger.error(f"Unknown device type: {device_type}")
            return None

    def total_power_generated(self):
        """
        Oblicza całkowitą moc generowaną przez wszystkie aktywne urządzenia w mikrosieci.

        Returns:
            float: Suma mocy generowanej przez wszystkie aktywne urządzenia w kW.
        """
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
        """
        Zwraca listę wszystkich urządzeń generujących moc w mikrosieci.

        Returns:
            list: Lista wszystkich urządzeń (z wyłączeniem BESS).
        """
        # Ta metoda zwraca listę wszystkich urządzeń generujących moc
        return (
            self.pv_panels + self.wind_turbines + self.fuel_turbines + self.fuel_cells
        )

    def get_active_devices(self):
        """
        Zwraca listę wszystkich aktywnych (online) urządzeń generujących moc.

        Returns:
            list: Lista aktywnych urządzeń.

        Notes:
            Metoda również wypisuje informacje o aktywnych urządzeniach do konsoli.
        """
        active_devices = [
            device
            for device in self.get_all_devices()
            if device.get_status() == "online"
        ]

        return active_devices

    def get_inactive_devices(self):
        """
        Zwraca listę wszystkich nieaktywnych (offline) urządzeń generujących moc.

        Returns:
            list: Lista nieaktywnych urządzeń.

        Notes:
            Metoda również wypisuje liczbę nieaktywnych urządzeń do konsoli.
        """
        inactive_devices = [
            device
            for device in self.get_all_devices()
            if device.get_status() == "offline"
        ]

        return inactive_devices

    def has_inactive_devices(self):
        """
        Sprawdza, czy w mikrosieci są jakiekolwiek nieaktywne urządzenia.

        Returns:
            bool: True, jeśli są nieaktywne urządzenia, False w przeciwnym razie.
        """

        return len(self.get_inactive_devices()) > 0

    def load_data_from_json(self, file_path):
        """
        Wczytuje dane urządzeń z pliku JSON i aktualizuje/dodaje je do mikrosieci.

        Args:
            file_path (str): Ścieżka do pliku JSON zawierającego dane urządzeń.

        Notes:
            Metoda obsługuje błędy związane z odczytem pliku i przetwarzaniem JSON.
            W przypadku błędu wyświetla odpowiedni komunikat.
        """
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

            self.info_logger.info("Data loaded successfully.")
        except FileNotFoundError as e:
            self.error_logger.error(f"Error: {e}")
        except json.JSONDecodeError:
            self.error_logger.error(f"Error: Invalid JSON format in file {file_path}")
        except Exception as e:
            self.error_logger.error(f"An unexpected error occurred: {e}")
