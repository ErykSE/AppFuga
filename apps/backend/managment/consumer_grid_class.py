import json

from apps.backend.devices.adjustable_devices import AdjustableDevice
from apps.backend.devices.non_adjustable import NonAdjustableDevice


class EnergyConsumerGrid:
    """
    Główna klasa zarządzająca urządzeniami/odbiorami, które mają zapotrzebowanie na moc.

    Klasa ta odpowiada za przechowywanie, dodawanie, aktualizację i zarządzanie
    różnymi typami urządzeń konsumujących energię, w tym urządzeniami regulowanymi
    i nieregulowanymi.

    Attributes:
        non_adjustable_devices (list): Lista obiektów reprezentujących urządzenia nieregulowane.
        adjustable_devices (list): Lista obiektów reprezentujących urządzenia regulowane.
    """

    def __init__(self):
        self.non_adjustable_devices = []
        self.adjustable_devices = []

    def add_device(self, device, device_type):
        """
        Dodaje nowe urządzenie do odpowiedniej listy w zależności od typu urządzenia.

        Args:
            device (object): Obiekt reprezentujący urządzenie do dodania.
            device_type (str): Typ urządzenia ('non_adjustable_device' lub 'adjustable_device').

        Notes:
            Metoda sprawdza poprawność urządzenia przed dodaniem go do listy.
            W przypadku nieprawidłowego urządzenia lub nieznanego typu, wyświetla odpowiedni komunikat.
        """
        if device_type == "non_adjustable_device":
            if device.is_valid:
                self.non_adjustable_devices.append(device)
            else:
                print(f"Invalid Non Adjustable Device: {device.name}")
        elif device_type == "adjustable_device":
            if device.is_valid:
                self.adjustable_devices.append(device)
            else:
                print(f"Invalid Adjustable Device: {device.name}")
        else:
            print(f"Unknown device type: {device_type}")

    def update_device(self, device_data, device_type):
        """
        Aktualizuje istniejące urządzenie lub dodaje nowe, jeśli nie istnieje.

        Args:
            device_data (dict): Słownik zawierający dane urządzenia do aktualizacji.
            device_type (str): Typ urządzenia ('non_adjustable_device' lub 'adjustable_device').

        Notes:
            Metoda sprawdza, czy urządzenie o danym ID już istnieje. Jeśli tak, aktualizuje jego dane.
            Jeśli nie, tworzy nowe urządzenie i dodaje je do odpowiedniej listy.
        """
        for device in getattr(self, f"{device_type}s"):
            if device.id == device_data["id"]:
                for key, value in device_data.items():
                    setattr(device, key, value)
                print(f"{device.name} updated successfully.")
                return
        new_device = self.create_device_instance(device_data, device_type)
        self.add_device(new_device, device_type)

    def create_device_instance(self, device_data, device_type):
        """
        Tworzy nową instancję urządzenia na podstawie podanych danych.

        Args:
            device_data (dict): Słownik zawierający dane do utworzenia urządzenia.
            device_type (str): Typ urządzenia do utworzenia ('non_adjustable_device' lub 'adjustable_device').

        Returns:
            object or None: Nowa instancja urządzenia lub None w przypadku nieznanego typu urządzenia.

        Notes:
            W przypadku nieznanego typu urządzenia, metoda wyświetla komunikat o błędzie.
        """
        if device_type == "non_adjustable_device":
            return NonAdjustableDevice.create_instance(device_data)
        elif device_type == "adjustable_device":
            return AdjustableDevice.create_instance(device_data)
        else:
            print(f"Unknown device type: {device_type}")
            return None

    def get_all_devices(self):
        """
        Zwraca listę wszystkich urządzeń konsumujących energię.

        Returns:
            list: Lista wszystkich urządzeń.
        """

        return self.non_adjustable_devices + self.adjustable_devices

    def get_active_devices(self):
        """
        Zwraca listę wszystkich aktywnych (online) urządzeń konsumujących energię.

        Returns:
            list: Lista aktywnych urządzeń.
        """
        return [
            device
            for device in self.get_all_devices()
            if device.get_switch_status() == True
        ]

    def total_power_consumed(self):
        """
        Oblicza całkowitą moc konsumowaną przez wszystkie aktywne urządzenia w sieci.

        Returns:
            float: Suma mocy konsumowanej przez wszystkie aktywne urządzenia w kW.
        """

        active_devices = self.get_active_devices()
        return sum(device.get_current_power() for device in active_devices)

    def load_data_from_json(self, file_path):
        """
        Wczytuje dane urządzeń z pliku JSON i aktualizuje/dodaje je do sieci konsumentów.

        Args:
            file_path (str): Ścieżka do pliku JSON zawierającego dane urządzeń.

        Notes:
            Metoda obsługuje zarówno urządzenia regulowane, jak i nieregulowane.
            Dla każdego urządzenia w pliku JSON, metoda wywołuje update_device().
        """
        with open(file_path, "r") as file:
            data = json.load(file)
        for device_type in ["non_adjustable_device", "adjustable_device"]:
            for device_data in data.get(f"{device_type}s", []):
                self.update_device(device_data, device_type)

        print(f"[DEBUG] Loaded devices:")
        print(f"[DEBUG] Adjustable devices: {len(self.adjustable_devices)}")
        for device in self.adjustable_devices:
            print(
                f"[DEBUG]   - {device.name}: Power={device.power}, Status={device.switch_status}"
            )
        print(f"[DEBUG] Non-adjustable devices: {len(self.non_adjustable_devices)}")
        for device in self.non_adjustable_devices:
            print(
                f"[DEBUG]   - {device.name}: Power={device.power}, Status={device.switch_status}"
            )
