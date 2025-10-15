class EnergyPoint:
    """
    Główna klasa dla urządzeń/odbiorów, które zużywają moc.
    Dziedziczyć z niej będą klasy: AdjustableDevice oraz NonAdjustableDevice.
    
    ZAKTUALIZOWANA:
    - Dodano: setpoint_output (wartość zadana)
    - Dodano: actual_output (rzeczywista wartość)
    - Dodano: from_dict() do ładowania z JSON
    - Dodano: loggery
    """

    def __init__(
        self,
        id,
        name,
        priority,
        power,
        switch_status,
        actual_output=None,  # NOWE: rzeczywista wartość z SCADA
        setpoint_output=None,  # NOWE: wartość zadana
        info_logger=None,  # NOWE
        error_logger=None,  # NOWE
    ):
        self.id = id
        self.name = name
        self.priority = priority
        self.power = power  # Nominalna moc
        
        # NOWE: jeśli nie podano, użyj power jako domyślnej wartości
        self.actual_output = actual_output if actual_output is not None else power
        self.setpoint_output = setpoint_output if setpoint_output is not None else power
        
        self.switch_status = switch_status
        self.is_valid = False
        
        # NOWE: Loggery
        self.info_logger = info_logger
        self.error_logger = error_logger

    @staticmethod
    def validate_data(data):
        """
        Waliduje dane urządzenia.
        ZAKTUALIZOWANA: użyto loggerów, dodano walidację nowych pól.
        """
        required_keys = [
            "id",
            "name",
            "priority",
            "power",
            "switch_status",
        ]
        
        for key in required_keys:
            if key not in data:
                print(f"Missing key: {key} in data: {data}")
                return False
        
        if not isinstance(data["id"], int) or data["id"] <= 0:
            print(f"Invalid id: {data['id']}")
            return False
        if not isinstance(data["name"], str) or not data["name"]:
            print(f"Invalid name: {data['name']}")
            return False
        if not isinstance(data["priority"], int) or data["priority"] < 0:
            print(f"Invalid priority: {data['priority']}")
            return False
        if not isinstance(data["power"], (int, float)) or data["power"] < 0:
            print(f"Invalid power: {data['power']}")
            return False
        if not isinstance(data["switch_status"], bool):
            print(f"Invalid switch_status: {data['switch_status']}")
            return False
        
        return True

    @classmethod
    def create_instance(cls, data, info_logger=None, error_logger=None):
        """
        Tworzy instancję z walidacją.
        ZAKTUALIZOWANA: dodano loggery.
        """
        if cls.validate_data(data):
            # Dodaj loggery do danych
            data['info_logger'] = info_logger
            data['error_logger'] = error_logger
            
            instance = cls(**data)
            instance.is_valid = True
            return instance
        return None

    @classmethod
    def from_dict(cls, data, info_logger=None, error_logger=None):
        """
        NOWA METODA: Tworzy instancję EnergyPoint ze słownika (z JSON API).
        
        To jest FABRYKA - automatycznie mapuje dane z API na obiekt Python.
        
        Args:
            data (dict): Słownik z danymi z API
            info_logger: Logger do informacji
            error_logger: Logger do błędów
            
        Returns:
            EnergyPoint: Nowa instancja urządzenia
        """
        return cls(
            id=data.get("id"),
            name=data.get("name"),
            priority=data.get("priority", 10),  # Domyślny priorytet
            power=data.get("power", 0),
            switch_status=data.get("switch_status", True),
            actual_output=data.get("actual_output"),  # Z SCADA
            setpoint_output=data.get("setpoint_output"),  # Wartość zadana
            info_logger=info_logger,
            error_logger=error_logger
        )

    def get_current_power(self):
        """
        Zwraca aktualną moc zużywaną.
        ZAKTUALIZOWANA: używa actual_output lub power.
        """
        if not self.switch_status:
            return 0
        return self.actual_output if self.actual_output is not None else self.power

    def get_switch_status(self):
        """Zwraca status włączenia."""
        return self.switch_status

    def activate(self):
        """
        Aktywuje urządzenie.
        ZAKTUALIZOWANA: użyto loggerów.
        """
        self.switch_status = True
        
        if self.info_logger:
            self.info_logger.info(f"{self.name} activated")
        else:
            print(f"{self.name} activated")

    def deactivate(self):
        """
        Dezaktywuje urządzenie.
        ZAKTUALIZOWANA: zeruje setpoint, użyto loggerów.
        """
        if self.switch_status:
            self.switch_status = False
            self.power = 0
            self.setpoint_output = 0  # NOWE: wyzeruj setpoint
            
            if self.info_logger:
                self.info_logger.info(f"{self.name} deactivated")
            else:
                print(f"{self.name} deactivated")
            
            return True
        else:
            if self.info_logger:
                self.info_logger.info(f"{self.name} is already deactivated")
            else:
                print(f"{self.name} is already deactivated")
            
            return False

    def to_dict(self):
        """
        Konwertuje obiekt do słownika (do zapisu JSON).
        ZAKTUALIZOWANA: dodano nowe pola.
        """
        return {
            "id": self.id,
            "name": self.name,
            "priority": self.priority,
            "power": self.power,
            "actual_output": self.actual_output,  # NOWE
            "setpoint_output": self.setpoint_output,  # NOWE
            "switch_status": self.switch_status,
        }

    def get_actual_output(self):
        """
        Zwraca rzeczywistą moc wyjściową.
        ZAKTUALIZOWANA: zwraca actual_output lub 0.
        """
        if not self.switch_status:
            return 0
        return self.actual_output if self.actual_output is not None else self.power

    def __str__(self):
        """Reprezentacja tekstowa obiektu."""
        status = "ON" if self.switch_status else "OFF"
        return (
            f"{self.name} (ID: {self.id}): "
            f"power={self.get_current_power():.2f} kW, "
            f"Status: {status}"
        )

    def __repr__(self):
        """Reprezentacja deweloperska obiektu."""
        return (
            f"EnergyPoint(id={self.id}, name='{self.name}', "
            f"priority={self.priority}, power={self.power}, "
            f"actual_output={self.actual_output}, "
            f"switch_status={self.switch_status})"
        )