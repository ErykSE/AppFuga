import json

from apps.backend.devices.adjustable_devices import AdjustableDevice
from apps.backend.devices.non_adjustable import NonAdjustableDevice


class EnergyConsumerGrid:
    """
    Główna klasa zarządzająca urządzeniami/odbiorami, które mają zapotrzebowanie na moc.

    Klasa ta odpowiada za przechowywanie, dodawanie, aktualizację i zarządzanie
    różnymi typami urządzeń konsumujących energię, w tym urządzeniami regulowanymi
    i nieregulowanymi.
    
    ZAKTUALIZOWANA: Dodano wsparcie dla loggerów i metody from_dict().

    Attributes:
        non_adjustable_devices (list): Lista obiektów reprezentujących urządzenia nieregulowane.
        adjustable_devices (list): Lista obiektów reprezentujących urządzenia regulowane.
        info_logger: Logger do informacji (opcjonalny)
        error_logger: Logger do błędów (opcjonalny)
    """

    def __init__(self, info_logger=None, error_logger=None):
        self.non_adjustable_devices = []
        self.adjustable_devices = []
        self.info_logger = info_logger  # NOWE
        self.error_logger = error_logger  # NOWE

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
                msg = f"Invalid Non Adjustable Device: {device.name}"
                if self.error_logger:
                    self.error_logger.error(msg)
                else:
                    print(msg)
        elif device_type == "adjustable_device":
            if device.is_valid:
                self.adjustable_devices.append(device)
            else:
                msg = f"Invalid Adjustable Device: {device.name}"
                if self.error_logger:
                    self.error_logger.error(msg)
                else:
                    print(msg)
        else:
            msg = f"Unknown device type: {device_type}"
            if self.error_logger:
                self.error_logger.error(msg)
            else:
                print(msg)

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
                
                msg = f"{device.name} updated successfully."
                if self.info_logger:
                    self.info_logger.info(msg)
                else:
                    print(msg)
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
            return NonAdjustableDevice.create_instance(
                device_data, 
                self.info_logger, 
                self.error_logger
            )
        elif device_type == "adjustable_device":
            return AdjustableDevice.create_instance(
                device_data,
                self.info_logger,
                self.error_logger
            )
        else:
            msg = f"Unknown device type: {device_type}"
            if self.error_logger:
                self.error_logger.error(msg)
            else:
                print(msg)
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
        Ładuje dane urządzeń konsumpcyjnych z pliku JSON.
        
        ZAKTUALIZOWANA: Używa from_dict() zamiast ręcznego mapowania.
        
        Args:
            file_path (str): Ścieżka do pliku JSON z danymi
        """
        try:
            with open(file_path, "r") as file:
                data = json.load(file)
            
            if self.info_logger:
                self.info_logger.info(f"Loading consumer grid data from {file_path}")
            else:
                print(f"Loading consumer grid data from {file_path}")
            
            # Wyczyść istniejące urządzenia
            self.non_adjustable_devices = []
            self.adjustable_devices = []
            
            # Załaduj urządzenia nieregulowane
            if "non_adjustable_devices" in data:
                for device_data in data["non_adjustable_devices"]:
                    device = NonAdjustableDevice.from_dict(
                        device_data,
                        self.info_logger,
                        self.error_logger
                    )
                    if device:
                        device.is_valid = True  # Oznacz jako zwalidowane
                        self.non_adjustable_devices.append(device)
                
                if self.info_logger:
                    self.info_logger.info(
                        f"Loaded {len(self.non_adjustable_devices)} non-adjustable devices"
                    )
                else:
                    print(f"Loaded {len(self.non_adjustable_devices)} non-adjustable devices")
            
            # Załaduj urządzenia regulowane
            if "adjustable_devices" in data:
                for device_data in data["adjustable_devices"]:
                    device = AdjustableDevice.from_dict(
                        device_data,
                        self.info_logger,
                        self.error_logger
                    )
                    if device:
                        device.is_valid = True  # Oznacz jako zwalidowane
                        self.adjustable_devices.append(device)
                
                if self.info_logger:
                    self.info_logger.info(
                        f"Loaded {len(self.adjustable_devices)} adjustable devices"
                    )
                else:
                    print(f"Loaded {len(self.adjustable_devices)} adjustable devices")
            
            # Loguj szczegóły załadowanych urządzeń
            self._log_loading_summary()
            
            return True
            
        except FileNotFoundError:
            msg = f"File not found: {file_path}"
            if self.error_logger:
                self.error_logger.error(msg)
            else:
                print(msg)
            return False
        except json.JSONDecodeError as e:
            msg = f"JSON decode error in {file_path}: {str(e)}"
            if self.error_logger:
                self.error_logger.error(msg)
            else:
                print(msg)
            return False
        except Exception as e:
            msg = f"Error loading data from {file_path}: {str(e)}"
            if self.error_logger:
                self.error_logger.error(msg)
            else:
                print(msg)
            return False

    def _log_loading_summary(self):
        """
        NOWA METODA: Loguje podsumowanie załadowanych urządzeń.
        """
        total_devices = len(self.non_adjustable_devices) + len(self.adjustable_devices)
        
        if self.info_logger:
            self.info_logger.info("=== Consumer Grid Loading Summary ===")
            self.info_logger.info(f"Total devices loaded: {total_devices}")
            self.info_logger.info(f"  - Non-adjustable: {len(self.non_adjustable_devices)}")
            self.info_logger.info(f"  - Adjustable: {len(self.adjustable_devices)}")
            
            # Szczegóły urządzeń nieregulowanych
            if self.non_adjustable_devices:
                self.info_logger.info("Non-adjustable devices:")
                for device in self.non_adjustable_devices:
                    self.info_logger.info(
                        f"  - {device.name}: {device.get_current_power():.2f} kW, "
                        f"status={'ON' if device.switch_status else 'OFF'}"
                    )
            
            # Szczegóły urządzeń regulowanych
            if self.adjustable_devices:
                self.info_logger.info("Adjustable devices:")
                for device in self.adjustable_devices:
                    self.info_logger.info(
                        f"  - {device.name}: {device.get_current_power():.2f} kW "
                        f"(range: {device.min_power:.2f}-{device.max_power:.2f} kW), "
                        f"status={'ON' if device.switch_status else 'OFF'}"
                    )
        else:
            print("=== Consumer Grid Loading Summary ===")
            print(f"Total devices loaded: {total_devices}")
            print(f"  - Non-adjustable: {len(self.non_adjustable_devices)}")
            print(f"  - Adjustable: {len(self.adjustable_devices)}")