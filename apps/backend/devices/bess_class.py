import time


class BESS:
    """
    Klasa dla urządzenia magazynującego energię (Battery Energy Storage System).
    
    ZAKTUALIZOWANA zgodnie z nowym API C#:
    - Dodano: actual_output, setpoint_output
    - Dodano: max_discharge_power, max_charge_power, max_charge_level
    - Dodano: wsparcie dla loggerów (zamiast print)
    - Dodano: metodę from_dict() do ładowania z JSON
    """

    def __init__(
        self,
        id,
        name,
        capacity,
        min_charge_level,
        max_charge_level=None,  # NOWE: dodane
        charge_level=0,
        max_discharge_power=None,  # NOWE: dodane
        max_charge_power=None,  # NOWE: dodane
        min_output=0,  # NOWE: dodane
        actual_output=0,  # NOWE: dodane - rzeczywista moc z SCADA
        setpoint_output=0,  # NOWE: dodane - wartość zadana
        switch_status=False,
        device_status="offline",
        info_logger=None,  # NOWE: dodane
        error_logger=None,  # NOWE: dodane
    ):
        self.id = id
        self.name = name
        self.capacity = capacity
        self.min_charge_level = min_charge_level
        
        # NOWE: jeśli nie podano max_charge_level, ustaw na capacity
        self.max_charge_level = max_charge_level if max_charge_level is not None else capacity
        
        self.charge_level = charge_level
        
        # NOWE: jeśli nie podano limitów mocy, ustaw na capacity (bezpieczna wartość)
        self.max_discharge_power = max_discharge_power if max_discharge_power is not None else capacity
        self.max_charge_power = max_charge_power if max_charge_power is not None else capacity
        self.min_output = min_output
        
        # NOWE: pola dla komunikacji z SCADA
        self.actual_output = actual_output  # Rzeczywista moc z SCADA
        self.setpoint_output = setpoint_output  # Wartość zadana (ujemna=ładowanie, dodatnia=rozładowanie)
        
        self.switch_status = switch_status
        self.device_status = device_status
        self.is_valid = False
        
        # NOWE: loggery
        self.info_logger = info_logger
        self.error_logger = error_logger

    @staticmethod
    def validate_data(data):
        """
        Waliduje dane BESS.
        ZAKTUALIZOWANA: dodano walidację nowych pól.
        """
        errors = []
        
        # Wymagane pola podstawowe
        required_keys = [
            "id",
            "name",
            "capacity",
            "min_charge_level",
            "charge_level",
            "switch_status",
            "device_status",
        ]
        
        for key in required_keys:
            if key not in data:
                errors.append(f"Missing key: {key}")
        
        # Walidacja ID
        if not isinstance(data.get("id"), int) or data.get("id", 0) <= 0:
            errors.append(f"Invalid id: {data.get('id')}")
        
        # Walidacja nazwy
        if not isinstance(data.get("name"), str) or not data.get("name"):
            errors.append(f"Invalid name: {data.get('name')}")
        
        # Walidacja capacity
        if not isinstance(data.get("capacity"), (int, float)) or data.get("capacity", 0) < 0:
            errors.append(f"Invalid capacity: {data.get('capacity')}")
        
        # Walidacja charge_level
        if not isinstance(data.get("charge_level"), (int, float)) or data.get("charge_level", 0) < 0:
            errors.append(f"Invalid charge_level: {data.get('charge_level')}")
        
        # Walidacja switch_status
        if not isinstance(data.get("switch_status"), bool):
            errors.append(f"Invalid switch_status: {data.get('switch_status')}")
        
        # Walidacja device_status
        if data.get("device_status") not in ["online", "offline", "operational", "off"]:
            errors.append(f"Invalid device_status: {data.get('device_status')}")
        
        # Walidacja min_charge_level
        capacity = data.get("capacity", 0)
        min_charge = data.get("min_charge_level", 0)
        if min_charge < 0 or min_charge > capacity:
            errors.append(f"Invalid min_charge_level: {min_charge}")
        
        # Walidacja charge_level vs min_charge_level
        charge_level = data.get("charge_level", 0)
        if charge_level < min_charge:
            errors.append(f"Charge level ({charge_level}) cannot be lower than min_charge_level ({min_charge})")
        
        # NOWE: Walidacja max_charge_level
        max_charge = data.get("max_charge_level", capacity)
        if max_charge > capacity:
            errors.append(f"max_charge_level ({max_charge}) cannot exceed capacity ({capacity})")
        
        # NOWE: Walidacja limitów mocy
        max_discharge = data.get("max_discharge_power")
        if max_discharge is not None and (not isinstance(max_discharge, (int, float)) or max_discharge < 0):
            errors.append(f"Invalid max_discharge_power: {max_discharge}")
        
        max_charge_power = data.get("max_charge_power")
        if max_charge_power is not None and (not isinstance(max_charge_power, (int, float)) or max_charge_power < 0):
            errors.append(f"Invalid max_charge_power: {max_charge_power}")

        return errors

    @classmethod
    def create_instance(cls, data, info_logger=None, error_logger=None):
        """
        Tworzy instancję BESS z walidacją.
        ZAKTUALIZOWANA: dodano loggery jako parametry.
        """
        errors = cls.validate_data(data)
        
        if not errors:
            # Dodaj loggery do danych
            data['info_logger'] = info_logger
            data['error_logger'] = error_logger
            
            instance = cls(**data)
            instance.is_valid = True
            
            if info_logger:
                info_logger.info(f"Successfully created BESS instance: {instance.name}")
            else:
                print(f"Successfully created BESS instance: {instance.name}")
            
            return instance
        else:
            error_msg = f"Failed to create BESS instance. Errors: {errors}"
            if error_logger:
                error_logger.error(error_msg)
            else:
                print(error_msg)
            return None

    @classmethod
    def from_dict(cls, data, info_logger=None, error_logger=None):
        """
        NOWA METODA: Tworzy instancję BESS ze słownika (z JSON API).
        Zgodna z nowym formatem API C#.
        """
        return cls(
            id=data.get("id"),
            name=data.get("name"),
            capacity=data.get("capacity"),
            min_charge_level=data.get("min_charge_level", 0),
            max_charge_level=data.get("max_charge_level", data.get("capacity")),
            charge_level=data.get("charge_level", 0),
            max_discharge_power=data.get("max_discharge_power"),
            max_charge_power=data.get("max_charge_power"),
            min_output=data.get("min_output", 0),
            actual_output=data.get("actual_output", 0),
            setpoint_output=data.get("setpoint_output", 0),
            switch_status=data.get("switch_status", True),
            device_status=data.get("device_status", "offline"),
            info_logger=info_logger,
            error_logger=error_logger
        )

    def activate(self):
        """
        Aktywuje BESS (włącza).
        """
        if self.charge_level > self.min_charge_level:
            self.device_status = "operational"  # Zmienione z "online" na "operational" (zgodne z API)
            self.switch_status = True
            
            if self.info_logger:
                self.info_logger.info(f"BESS {self.name} activated")
            else:
                print(f"BESS {self.name} activated")
            
            return True
        
        if self.error_logger:
            self.error_logger.warning(f"Cannot activate BESS {self.name} - charge level too low")
        else:
            print(f"Cannot activate BESS {self.name} - charge level too low")
        
        return False

    def deactivate(self):
        """
        Dezaktywuje BESS (wyłącza).
        ZAKTUALIZOWANA: zeruje setpoint_output.
        """
        self.device_status = "off"  # Zmienione z "offline" na "off"
        self.switch_status = False
        self.setpoint_output = 0  # NOWE: wyzeruj setpoint
        
        if self.info_logger:
            self.info_logger.info(f"BESS {self.name} deactivated")
        else:
            print(f"BESS {self.name} deactivated")
        
        return True

    def charge(self, power):
        """
        Ustawia BESS na ładowanie.
        
  WAŻNE: Ta metoda NIE zmienia charge_level!
        charge_level jest READ-ONLY z SCADA i zostanie zaktualizowany
        w następnej iteracji przez load_data_from_json().
        
        Args:
            power (float): Moc ładowania w kW (wartość dodatnia)
            
        Returns:
            tuple: (moc ładowania w kW, procent dla info)
        """
        if not self.switch_status:
            if self.info_logger:
                self.info_logger.warning(f"BESS {self.name} is turned off, cannot charge")
            return 0, 0

        # Ogranicz do max_charge_power
        actual_power = min(power, self.max_charge_power)
        
        # Sprawdź dostępną przestrzeń
        available_space = self.max_charge_level - self.charge_level
        
        if available_space <= 0:
            if self.info_logger:
                self.info_logger.info(f"BESS {self.name} is fully charged")
            self.setpoint_output = 0
            return 0, 0

        # Ogranicz moc do dostępnej przestrzeni
        # UWAGA: available_space jest w kWh, więc musimy obliczyć ile mocy możemy załadować
        # Zakładając czas iteracji (np. 5 min = 0.0833 h)
        # Jeśli mamy 70 kWh dostępnej przestrzeni i 5 min iteracji:
        # max_power = 70 kWh / 0.0833 h = 840 kW
        # Ale to jest niepraktyczne, więc po prostu używamy actual_power
        # (BESSCapabilityChecker już to sprawdził)
        
        #  TYLKO ustaw setpoint (polecenie dla SCADA)
        self.setpoint_output = -abs(actual_power)  # Ujemny = ładowanie
        charged_amount = actual_power  # kW
        
        #  NIE ZMIENIAJ charge_level!
        # self.charge_level += charged_amount  # ← USUNIĘTE!
        
        # Oblicz procent (informacyjnie, bazując na OBECNYM charge_level)
        charged_percent = (charged_amount / self.capacity) * 100
        
        # Log dla operatora
        if self.info_logger:
            self.info_logger.info(
                f"BESS {self.name} - setpoint set to {self.setpoint_output:.2f} kW (charging)"
            )
            self.info_logger.info(f"  Current charge_level: {self.charge_level:.2f} kWh (will be updated by SCADA)")
        
        return charged_amount, charged_percent

    def discharge(self, power):
        """
        Ustawia BESS na rozładowanie.
        
  WAŻNE: Ta metoda NIE zmienia charge_level!
        charge_level jest READ-ONLY z SCADA i zostanie zaktualizowany
        w następnej iteracji przez load_data_from_json().
        
        Args:
            power (float): Moc rozładowania w kW (wartość dodatnia)
            
        Returns:
            tuple: (moc rozładowania w kW, procent dla info)
        """
        if not self.switch_status:
            if self.info_logger:
                self.info_logger.warning(f"BESS {self.name} is turned off, cannot discharge")
            return 0, 0

        # Ogranicz do max_discharge_power
        actual_power = min(power, self.max_discharge_power)
        
        # Oblicz dostępną energię
        available_energy = self.charge_level - self.min_charge_level
        
        if available_energy <= 0:
            if self.info_logger:
                self.info_logger.info(f"BESS {self.name} reached minimum charge level")
            self.setpoint_output = 0
            return 0, 0

        # Ogranicz moc do dostępnej energii
        discharged_amount = min(actual_power, available_energy)
        
        #  TYLKO ustaw setpoint (polecenie dla SCADA)
        self.setpoint_output = abs(discharged_amount)  # Dodatni = rozładowanie
        
        #  NIE ZMIENIAJ charge_level!
        # self.charge_level -= discharged_amount  # ← USUNIĘTE!
        
        # Oblicz procent (informacyjnie)
        discharged_percent = (discharged_amount / self.capacity) * 100
        
        # Log dla operatora
        if self.info_logger:
            self.info_logger.info(
                f"BESS {self.name} - setpoint set to {self.setpoint_output:.2f} kW (discharging)"
            )
            self.info_logger.info(f"  Current charge_level: {self.charge_level:.2f} kWh (will be updated by SCADA)")
        
        return discharged_amount, discharged_percent

    def get_charge_level(self):
        """Zwraca aktualny poziom naładowania."""
        return self.charge_level

    def get_capacity(self):
        """Zwraca całkowitą pojemność BESS."""
        return self.capacity

    def get_status(self):
        """Zwraca status operacyjny urządzenia."""
        return self.device_status

    def get_switch_status(self):
        """Zwraca status włączenia."""
        return self.switch_status

    def get_available_energy(self):
        """Zwraca dostępną energię do rozładowania."""
        return max(0, self.charge_level - self.min_charge_level)
    
    def get_free_capacity(self):
        """NOWA METODA: Zwraca wolną pojemność do naładowania."""
        return max(0, self.max_charge_level - self.charge_level)

    def is_uncharged(self):
        """Sprawdza czy BESS ma miejsce na ładowanie."""
        return self.charge_level < self.max_charge_level  # ZMIENIONE: użyj max_charge_level
    
    def is_charged(self):
        """NOWA METODA: Sprawdza czy BESS ma energię do rozładowania."""
        return self.charge_level > self.min_charge_level

    def to_dict(self):
        """
        Konwertuje obiekt BESS do słownika dla API.
        
  WAŻNE: Wysyłamy TYLKO setpointy (polecenia dla SCADA)!
        charge_level i actual_output są READ-ONLY i NIE są wysyłane.
        
        Returns:
            dict: Słownik z poleceniami dla SCADA
        """
        return {
            "id": self.id,
            "name": self.name,
            
            #  SETPOINTY (polecenia dla SCADA) - WYSYŁAMY:
            "setpoint_output": self.setpoint_output,
            "switch_status": self.switch_status,
            
            #  READ-ONLY (stan z SCADA) - NIE WYSYŁAMY:
            # "charge_level": self.charge_level,  # ← READ-ONLY
            # "actual_output": self.actual_output,  # ← READ-ONLY
            
            # ℹ️  METADATA (opcjonalne, dla kontekstu):
            "capacity": self.capacity,
            "min_charge_level": self.min_charge_level,
            "max_charge_level": self.max_charge_level,
            "max_discharge_power": self.max_discharge_power,
            "max_charge_power": self.max_charge_power,
            "min_output": self.min_output,
            "device_status": self.device_status,
        }

    def __repr__(self):
        """NOWA METODA: Reprezentacja tekstowa obiektu."""
        status = "ON" if self.switch_status else "OFF"
        return (
            f"BESS(name={self.name}, "
            f"charge={self.charge_level:.2f}/{self.capacity:.2f} kWh, "
            f"setpoint={self.setpoint_output:.2f} kW, "
            f"status={status})"
        )