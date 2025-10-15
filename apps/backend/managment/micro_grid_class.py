from apps.backend.devices.pv_class import PV
from apps.backend.devices.wind_turbine_class import WindTurbine
from apps.backend.devices.fuel_turbine_class import FuelTurbine
from apps.backend.devices.fuel_cell_class import FuelCell
from apps.backend.devices.bess_class import BESS
from apps.backend.devices.power_meter import PowerMeter

import json
import os


class Microgrid:
    """
    Główna klasa zarządzająca urządzeniami generującymi moc w mikrosieci.

    Klasa ta odpowiada za przechowywanie, dodawanie, aktualizację i zarządzanie
    różnymi typami urządzeń energetycznych, takimi jak panele fotowoltaiczne,
    turbiny wiatrowe, turbiny paliwowe, ogniwa paliwowe oraz system magazynowania
    energii (BESS).
    
    ZAKTUALIZOWANA: Używa from_dict() do ładowania urządzeń z JSON.

    Attributes:
        pv_panels (list): Lista obiektów reprezentujących panele fotowoltaiczne.
        wind_turbines (list): Lista obiektów reprezentujących turbiny wiatrowe.
        fuel_turbines (list): Lista obiektów reprezentujących turbiny paliwowe.
        fuel_cells (list): Lista obiektów reprezentujących ogniwa paliwowe.
        bess (BESS or None): Obiekt reprezentujący system magazynowania energii (BESS).
        power_meters (dict): Słownik mierników mocy.
        info_logger: Logger do informacji.
        error_logger: Logger do błędów.
    """

    def __init__(self, info_logger, error_logger):
        self.pv_panels = []
        self.wind_turbines = []
        self.fuel_turbines = []
        self.fuel_cells = []
        self.bess = None
        self.power_meters = {}
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
                #self.info_logger.info(
                    #f"Added BESS: {device.name} (Status: {device.device_status})"
                #)
            else:
                self.error_logger.error("BESS already exists. Cannot add another one.")
        else:
            device_list = getattr(self, f"{device_type}s")
            if device.is_valid:
                device_list.append(device)
                #self.info_logger.info(
                    #f"Added {device_type}: {device.name} (Status: {device.device_status})"
                #)
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
        #self.info_logger.info(
            #f"[DEBUG] Attempting to update {device_type}: {device_data}"
        #)

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
                #self.info_logger.info(f"BESS {self.bess.name} updated successfully.")
            elif self.bess is None:
                new_device = self.create_device_instance(device_data, device_type)
                if new_device:
                    self.bess = new_device
                    #self.info_logger.info(f"New BESS added: {new_device.name}")
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
                    #self.info_logger.info(
                        #f"{device_type.capitalize()} {device.name} updated successfully."
                    #)
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
            instance = device_class.create_instance(
                device_data,
                self.info_logger,
                self.error_logger
            )
            if instance:
                #self.info_logger.info(
                    #f"Successfully created {device_type} instance: {instance.name}"
                #)
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
        active_devices = self.get_active_devices()
        return sum(device.get_actual_output() for device in active_devices)

    def get_all_devices(self):
        """
        Zwraca listę wszystkich urządzeń generujących moc w mikrosieci.

        Returns:
            list: Lista wszystkich urządzeń (z wyłączeniem BESS).
        """
        return (
            self.pv_panels + self.wind_turbines + self.fuel_turbines + self.fuel_cells
        )

    def get_active_devices(self):
        """
        Zwraca listę wszystkich aktywnych (online/operational) urządzeń generujących moc.

        Returns:
            list: Lista aktywnych urządzeń.
        """
        active_devices = [
            device
            for device in self.get_all_devices()
            if device.get_status() in ["online", "operational"]  # ZAKTUALIZOWANE
        ]
        return active_devices

    def get_inactive_devices(self):
        """
        Zwraca listę wszystkich nieaktywnych (offline/off) urządzeń generujących moc.

        Returns:
            list: Lista nieaktywnych urządzeń.
        """
        inactive_devices = [
            device
            for device in self.get_all_devices()
            if device.get_status() in ["offline", "off"]  # ZAKTUALIZOWANE
        ]
        return inactive_devices

    def has_inactive_devices(self):
        """
        Sprawdza, czy w mikrosieci są jakiekolwiek nieaktywne urządzenia.

        Returns:
            bool: True, jeśli są nieaktywne urządzenia, False w przeciwnym razie.
        """
        return len(self.get_inactive_devices()) > 0

    def get_device_by_id(self, device_id):
        """
        NOWA METODA: Znajduje urządzenie po ID.
        
        Args:
            device_id: ID urządzenia do znalezienia
            
        Returns:
            object or None: Znalezione urządzenie lub None
        """
        # Sprawdź BESS
        if self.bess and self.bess.id == device_id:
            return self.bess
        
        # Sprawdź wszystkie pozostałe urządzenia
        for device in self.get_all_devices():
            if device.id == device_id:
                return device
        
        self.error_logger.warning(f"Device with ID {device_id} not found")
        return None

    def load_data_from_json(self, file_path):
        """
        Wczytuje dane urządzeń z pliku JSON i aktualizuje/dodaje je do mikrosieci.
        
        ZAKTUALIZOWANA: Używa from_dict() zamiast create_instance() + update_device().
        DODANO: Walidacja statusu SCADA.

        Args:
            file_path (str): Ścieżka do pliku JSON zawierającego dane urządzeń.

        Notes:
            Metoda obsługuje błędy związane z odczytem pliku i przetwarzaniem JSON.
            W przypadku błędu wyświetla odpowiedni komunikat.
        """
        try:
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"File not found: {file_path}")

            #self.info_logger.info(f"Loading microgrid data from {file_path}")

            with open(file_path, "r") as file:
                data = json.load(file)

            # ✅ WALIDACJA STATUSU SCADA
            if "status" in data:
                status = data.get("status", {})
                status_code = status.get("code", "unknown")
                
                if status_code == "scada_unavailable":
                    self.error_logger.critical(
                        "❌ SCADA SYSTEM NOT AVAILABLE! Cannot load data."
                    )
                    return False
                elif status_code == "partial_data":
                    missing = status.get("missing_devices", [])
                    self.error_logger.warning(
                        f"⚠️  Partial data received. Missing devices: {missing}"
                    )
                elif status_code == "ok":
                    self.info_logger.info("✅ SCADA status: OK")

            # Wyczyść istniejące urządzenia
            self.pv_panels = []
            self.wind_turbines = []
            self.fuel_turbines = []
            self.fuel_cells = []
            self.bess = None
            self.power_meters = {}

            # Załaduj panele PV
            if "pv_panels" in data:
                for pv_data in data["pv_panels"]:
                    pv = PV.from_dict(pv_data, self.info_logger, self.error_logger)
                    if pv:
                        pv.is_valid = True
                        self.pv_panels.append(pv)
                #self.info_logger.info(f"Loaded {len(self.pv_panels)} PV panels")

            # Załaduj turbiny wiatrowe
            if "wind_turbines" in data:
                for turbine_data in data["wind_turbines"]:
                    turbine = WindTurbine.from_dict(
                        turbine_data, self.info_logger, self.error_logger
                    )
                    if turbine:
                        turbine.is_valid = True
                        self.wind_turbines.append(turbine)
                #self.info_logger.info(f"Loaded {len(self.wind_turbines)} wind turbines")

            # Załaduj turbiny paliwowe
            if "fuel_turbines" in data:
                for turbine_data in data["fuel_turbines"]:
                    turbine = FuelTurbine.from_dict(
                        turbine_data, self.info_logger, self.error_logger
                    )
                    if turbine:
                        turbine.is_valid = True
                        self.fuel_turbines.append(turbine)
                #self.info_logger.info(f"Loaded {len(self.fuel_turbines)} fuel turbines")

            # Załaduj ogniwa paliwowe
            if "fuel_cells" in data:
                for cell_data in data["fuel_cells"]:
                    cell = FuelCell.from_dict(
                        cell_data, self.info_logger, self.error_logger
                    )
                    if cell:
                        cell.is_valid = True
                        self.fuel_cells.append(cell)
                #self.info_logger.info(f"Loaded {len(self.fuel_cells)} fuel cells")

            # Załaduj BESS
            if "bess" in data and isinstance(data["bess"], list) and len(data["bess"]) > 0:
                bess_data = data["bess"][0]  # Zakładamy jedno BESS
                self.bess = BESS.from_dict(
                    bess_data, self.info_logger, self.error_logger
                )
                if self.bess:
                    self.bess.is_valid = True
                    #self.info_logger.info(f"Loaded BESS: {self.bess.name}")

            # Załaduj mierniki mocy
            if "power_meters" in data:
                for meter_data in data["power_meters"]:
                    meter = PowerMeter.create_instance(meter_data)
                    if meter:
                        self.add_power_meter(meter)
                        #self.info_logger.info(
                            #f"Loaded power meter: {meter.name}, Status: {meter.status}, "
                            #f"Reading: {meter.measured_power} kW, Device ID: {meter.device_id}"
                        #)
                    else:
                        self.error_logger.warning(
                            f"Failed to create power meter: {meter_data}"
                        )

            # Loguj podsumowanie
            self._log_loading_summary()

            #self.info_logger.info("Microgrid data loaded successfully.")
            return True

        except FileNotFoundError as e:
            self.error_logger.error(f"Error: {e}")
            return False
        except json.JSONDecodeError:
            self.error_logger.error(f"Error: Invalid JSON format in file {file_path}")
            return False
        except Exception as e:
            self.error_logger.error(f"An unexpected error occurred: {e}")
            self.error_logger.exception("Full traceback:")
            return False

    def _log_loading_summary(self):
        """
        NOWA METODA: Loguje podsumowanie załadowanych urządzeń.
        """
        total_devices = (
            len(self.pv_panels) +
            len(self.wind_turbines) +
            len(self.fuel_turbines) +
            len(self.fuel_cells) +
            (1 if self.bess else 0)
        )

        #self.info_logger.info("=== Microgrid Loading Summary ===")
        #self.info_logger.info(f"Total devices loaded: {total_devices}")
        #self.info_logger.info(f"  - PV Panels: {len(self.pv_panels)}")
        #self.info_logger.info(f"  - Wind Turbines: {len(self.wind_turbines)}")
        #self.info_logger.info(f"  - Fuel Turbines: {len(self.fuel_turbines)}")
        #self.info_logger.info(f"  - Fuel Cells: {len(self.fuel_cells)}")
        #self.info_logger.info(f"  - BESS: {'Yes' if self.bess else 'No'}")
        #self.info_logger.info(f"  - Power Meters: {len(self.power_meters)}")

        '''

        # Szczegóły urządzeń
        for pv in self.pv_panels:
            self.info_logger.info(
                f"    PV: {pv.name} - actual={pv.actual_output:.2f} kW, "
                f"setpoint={pv.setpoint_output:.2f} kW, max={pv.max_output:.2f} kW, "
                f"status={'ON' if pv.switch_status else 'OFF'}"
            )

        for turbine in self.wind_turbines:
            self.info_logger.info(
                f"    Wind: {turbine.name} - actual={turbine.actual_output:.2f} kW, "
                f"setpoint={turbine.setpoint_output:.2f} kW, max={turbine.max_output:.2f} kW, "
                f"status={'ON' if turbine.switch_status else 'OFF'}"
            )

        for turbine in self.fuel_turbines:
            self.info_logger.info(
                f"    Fuel Turbine: {turbine.name} - actual={turbine.actual_output:.2f} kW, "
                f"setpoint={turbine.setpoint_output:.2f} kW, max={turbine.max_output:.2f} kW, "
                f"status={'ON' if turbine.switch_status else 'OFF'}"
            )

        for cell in self.fuel_cells:
            self.info_logger.info(
                f"    Fuel Cell: {cell.name} - actual={cell.actual_output:.2f} kW, "
                f"setpoint={cell.setpoint_output:.2f} kW, max={cell.max_output:.2f} kW, "
                f"status={'ON' if cell.switch_status else 'OFF'}"
            )

        if self.bess:
            self.info_logger.info(
                f"    BESS: {self.bess.name} - charge={self.bess.charge_level:.2f}/{self.bess.capacity:.2f} kWh, "
                f"actual_output={self.bess.actual_output:.2f} kW, "
                f"setpoint={self.bess.setpoint_output:.2f} kW, "
                f"status={'ON' if self.bess.switch_status else 'OFF'}"
            )
            '''

    def add_power_meter(self, power_meter):
        """Dodaje miernik mocy do mikrosieci."""
        if isinstance(power_meter, PowerMeter):
            self.power_meters[power_meter.device_id] = power_meter
            #self.info_logger.info(
                #f"Added power meter: {power_meter.name} for device ID: {power_meter.device_id}"
            #)
        else:
            self.error_logger.error(f"Invalid power meter object")

    def update_device_with_meter_data(self):
        """
        Aktualizuje urządzenia na podstawie odczytów z mierników mocy.
        
        ZAKTUALIZOWANA: Używa nowych statusów ("operational"/"off").
        """
        all_devices = self.get_all_devices()
        updated_devices = []
        
        #self.info_logger.info(
            #f"Checking {len(all_devices)} devices for updates based on meter readings"
        #)
        
        for device in all_devices:
            meter = self.power_meters.get(device.id)
            if meter:
                #self.info_logger.info(
                    #f"Checking device {device.name} (ID: {device.id}). "
                    #f"Device status: {device.device_status}, Meter status: {meter.status}, "
                    #f"Meter reading: {meter.measured_power} kW"
                #)
                
                # Sprawdź rozbieżność: urządzenie offline, ale miernik pokazuje moc
                if (
                    meter.status == "online"
                    and device.device_status in ["offline", "off"]
                    and meter.measured_power > 0
                ):
                    self.error_logger.error(
                        f"Communication error detected with {device.name} (ID: {device.id}). "
                        f"Device status is {device.device_status} but meter reading indicates "
                        f"power generation of {meter.measured_power} kW."
                    )
                    
                    # Aktualizuj urządzenie na podstawie miernika
                    device.actual_output = meter.measured_power
                    device.device_status = "operational"
                    device.switch_status = True
                    updated_devices.append(device)
                    
                    #self.info_logger.warning(
                        #f"Updated {device.name} status to operational and set actual output to "
                        #f"{meter.measured_power} kW based on meter reading. "
                       # f"Please check the device communication."
                    #)
                elif device.device_status in ["offline", "off"] and meter.measured_power > 0:
                    self.info_logger.warning(
                        f"{device.name} (ID: {device.id}) is {device.device_status} but meter "
                        f"reading indicates power generation. Meter status: {meter.status}, "
                        f"Meter reading: {meter.measured_power} kW. Device status not updated "
                        f"due to offline meter."
                    )
            else:
                self.info_logger.debug(
                    f"No meter found for device {device.name} (ID: {device.id})"
                )
        
        return updated_devices