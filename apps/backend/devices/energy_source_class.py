import time


class EnergySource:
    """
    Główna klasa dla urządzeń generujących moc.
    Dziedziczą z niej klasy: FuelCell, FuelTurbine, PV, WindTurbine.
    
    ZAKTUALIZOWANA zgodnie z nowym API C#:
    - Dodano: setpoint_output (wartość zadana dla SCADA)
    - Dodano: wsparcie dla loggerów
    - Dodano: metodę from_dict() do ładowania z JSON
    - Zaktualizowano: logikę set_output() i activate()
    """

    def __init__(
        self,
        id,
        name,
        priority,
        max_output,
        min_output,
        actual_output,
        switch_status,
        device_status,
        is_adjustable=False,
        setpoint_output=0,  # NOWE: wartość zadana
        info_logger=None,  # NOWE: logger
        error_logger=None,  # NOWE: logger
    ):
        self.id = id
        self.name = name
        self.priority = priority
        self.max_output = max_output
        self.min_output = min_output if is_adjustable else 0
        self.actual_output = actual_output  # Rzeczywista wartość z SCADA
        self.setpoint_output = setpoint_output  # NOWE: Wartość zadana
        self.switch_status = switch_status
        self.device_status = device_status
        self.is_valid = False
        self.pending_action = None
        self.action_approved = None
        self.action_request_time = None
        self.is_adjustable = is_adjustable
        
        # NOWE: Loggery
        self.info_logger = info_logger
        self.error_logger = error_logger

    @staticmethod
    def validate_data(data):
        """
        Waliduje dane urządzenia.
        ZAKTUALIZOWANA: dodano walidację setpoint_output.
        """
        errors = []
        required_keys = [
            "id",
            "name",
            "priority",
            "max_output",
            "min_output",
            "actual_output",
            "switch_status",
            "device_status",
        ]
        
        for key in required_keys:
            if key not in data:
                errors.append(f"Missing key: {key}")

        if not isinstance(data.get("id"), int) or data.get("id", 0) <= 0:
            errors.append(f"Invalid id: {data.get('id')}")
        if not isinstance(data.get("name"), str) or not data.get("name"):
            errors.append(f"Invalid name: {data.get('name')}")
        if not isinstance(data.get("priority"), int) or data.get("priority", 0) < 0:
            errors.append(f"Invalid priority: {data.get('priority')}")
        if (
            not isinstance(data.get("max_output"), (int, float))
            or data.get("max_output", 0) <= 0
        ):
            errors.append(f"Invalid max_output: {data.get('max_output')}")
        if (
            not isinstance(data.get("min_output"), (int, float))
            or data.get("min_output", 0) < 0
        ):
            errors.append(f"Invalid min_output: {data.get('min_output')}")
        if data.get("min_output", 0) > data.get("max_output", 0):
            errors.append(
                f"min_output ({data.get('min_output')}) is greater than max_output ({data.get('max_output')})"
            )
        if not isinstance(data.get("actual_output"), (int, float)):
            errors.append(f"Invalid actual_output: {data.get('actual_output')}")
        if not isinstance(data.get("switch_status"), bool):
            errors.append(f"Invalid switch_status: {data.get('switch_status')}")
        if data.get("device_status") not in ["online", "offline", "operational", "off"]:
            errors.append(f"Invalid device_status: {data.get('device_status')}")

        # NOWE: Walidacja setpoint_output (opcjonalne pole)
        if "setpoint_output" in data and not isinstance(data.get("setpoint_output"), (int, float)):
            errors.append(f"Invalid setpoint_output: {data.get('setpoint_output')}")

        # Jeśli urządzenie jest offline, pozwól na actual_output = 0
        if data.get("device_status") in ["offline", "off"] and data.get("actual_output") != 0:
            errors.append(
                f"Offline device should have actual_output = 0, got: {data.get('actual_output')}"
            )

        return errors

    @classmethod
    def create_instance(cls, data, info_logger=None, error_logger=None):
        """
        Tworzy instancję urządzenia z walidacją.
        ZAKTUALIZOWANA: dodano loggery.
        """
        errors = cls.validate_data(data)
        
        if not errors:
            # Dodaj loggery do danych
            data['info_logger'] = info_logger
            data['error_logger'] = error_logger
            
            instance = cls(**data)
            instance.is_valid = True
            
            if info_logger:
                info_logger.info(f"Successfully created {cls.__name__} instance: {instance.name}")
            else:
                print(f"Successfully created {cls.__name__} instance: {instance.name}")
            
            return instance
        else:
            error_msg = f"Failed to create {cls.__name__} instance. Errors: {errors}"
            if error_logger:
                error_logger.error(error_msg)
            else:
                print(error_msg)
            return None

    @classmethod
    def from_dict(cls, data, info_logger=None, error_logger=None):
        """
        NOWA METODA: Tworzy instancję urządzenia ze słownika (z JSON API).
        Zgodna z nowym formatem API C#.
        """
        return cls(
            id=data.get("id"),
            name=data.get("name"),
            priority=data.get("priority", 5),  # Domyślny priorytet
            max_output=data.get("max_output", 0),
            min_output=data.get("min_output", 0),
            actual_output=data.get("actual_output", 0),
            switch_status=data.get("switch_status", True),
            device_status=data.get("device_status", "offline"),
            is_adjustable=data.get("is_adjustable", True),
            setpoint_output=data.get("setpoint_output", 0),
            info_logger=info_logger,
            error_logger=error_logger
        )

    def get_actual_output(self):
        """
        Zwraca rzeczywistą moc wyjściową z SCADA.
        Jeśli urządzenie wyłączone, zwraca 0.
        """
        if not self.switch_status:
            return 0
        return self.actual_output

    def get_setpoint_output(self):
        """NOWA METODA: Zwraca wartość zadaną mocy."""
        return self.setpoint_output

    def get_max_output(self):
        """Zwraca maksymalną możliwą moc."""
        return self.max_output

    def get_min_output(self):
        """Zwraca minimalną możliwą moc."""
        return self.min_output if self.is_adjustable else 0

    def get_status(self):
        """Zwraca status operacyjny urządzenia."""
        return self.device_status

    def get_switch_status(self):
        """Zwraca status włączenia."""
        return self.switch_status

    def get_name(self):
        """Zwraca nazwę urządzenia."""
        return self.name
    
    def get_priority(self):
        """NOWA METODA: Zwraca priorytet urządzenia."""
        return self.priority

    def is_at_max_output(self):
        """Sprawdza czy urządzenie działa na maksymalnej mocy."""
        return self.actual_output >= self.max_output
    
    def can_increase_output(self):
        """NOWA METODA: Sprawdza czy można zwiększyć moc."""
        return self.switch_status and self.setpoint_output < self.max_output

    def can_decrease_output(self):
        """NOWA METODA: Sprawdza czy można zmniejszyć moc."""
        return self.switch_status and self.setpoint_output > self.min_output

    def activate(self):
        """
        Aktywuje urządzenie (włącza).
        ZAKTUALIZOWANA: użyto loggerów.
        """
        if self.device_status in ["offline", "off"]:
            self.device_status = "operational"  # Zmienione na "operational" (zgodne z API)
            self.switch_status = True
            
            if self.info_logger:
                self.info_logger.info(
                    f"{self.name} is now active with output {self.actual_output} kW."
                )
            else:
                print(f"{self.name} is now active with output {self.actual_output} kW.")
            
            return True
        
        if self.info_logger:
            self.info_logger.info(f"{self.name} is already active")
        
        return False

    def deactivate(self):
        """
        Dezaktywuje urządzenie (wyłącza).
        ZAKTUALIZOWANA: zeruje setpoint_output, użyto loggerów.
        """
        if self.device_status in ["online", "operational"]:
            self.device_status = "off"  # Zmienione na "off"
            self.actual_output = 0
            self.setpoint_output = 0  # NOWE: wyzeruj setpoint
            self.switch_status = False
            
            if self.info_logger:
                self.info_logger.info(f"{self.name} is now inactive.")
            else:
                print(f"{self.name} is now inactive.")
            
            return True
        
        if self.info_logger:
            self.info_logger.info(f"{self.name} is already inactive")
        
        return False

    def set_output(self, target_output):
        """
        Ustawia nową wartość mocy wyjściowej.
        
        ZAKTUALIZOWANA:
        - Ustawia setpoint_output (wartość zadaną)
        - Dodano logi
        - Lepsza walidacja
        
        Args:
            target_output (float): Nowa wartość mocy w kW
            
        Returns:
            bool: True jeśli sukces, False w przeciwnym razie
        """
        if self.info_logger:
            self.info_logger.info(
                f"Attempting to set output for {self.name} to {target_output} kW"
            )
        else:
            print(f"Attempting to set output for {self.name} to {target_output} kW")

        if self.device_status not in ["online", "operational"]:
            if self.error_logger:
                self.error_logger.warning(f"{self.name} is not active.")
            else:
                print(f"{self.name} is not active.")
            return False

        # Dla urządzeń nieregulowanych - tylko maksymalna moc
        if not self.is_adjustable and target_output != self.max_output:
            if self.error_logger:
                self.error_logger.warning(
                    f"{self.name} is not adjustable. Can only be set to maximum output."
                )
            else:
                print(f"{self.name} is not adjustable. Can only be set to maximum output.")
            return False

        # Walidacja zakresu
        if target_output < self.min_output:
            if self.error_logger:
                self.error_logger.warning(
                    f"{self.name}: Requested output {target_output} kW is below minimum {self.min_output} kW"
                )
            target_output = self.min_output
        elif target_output > self.max_output:
            if self.error_logger:
                self.error_logger.warning(
                    f"{self.name}: Requested output {target_output} kW exceeds maximum {self.max_output} kW"
                )
            target_output = self.max_output

        # Ustaw setpoint (SCADA użyje tej wartości)
        old_setpoint = self.setpoint_output
        self.setpoint_output = target_output
        
        if self.info_logger:
            self.info_logger.info(
                f"{self.name} setpoint changed: {old_setpoint:.2f} -> {target_output:.2f} kW"
            )
        else:
            print(f"{self.name} output set to {target_output} kW")
        
        return True

    def update_state(self, data):
        """
        Aktualizuje stan urządzenia nowymi danymi.
        ZAKTUALIZOWANA: użyto loggerów.
        """
        errors = self.validate_data(data)
        
        if not errors:
            for key, value in data.items():
                if key not in ['info_logger', 'error_logger']:  # Nie nadpisuj loggerów
                    setattr(self, key, value)
            
            if self.info_logger:
                self.info_logger.info(f"{self.name} state updated successfully.")
            else:
                print(f"{self.name} state updated successfully.")
            
            return True
        
        if self.error_logger:
            self.error_logger.error(
                f"Failed to update {self.name} state due to invalid data: {errors}"
            )
        else:
            print(f"Failed to update {self.name} state due to invalid data.")
        
        return False

    def to_dict(self):
        """
        Konwertuje obiekt do słownika (do zapisu JSON).
        ZAKTUALIZOWANA: dodano setpoint_output.
        """
        return {
            "id": self.id,
            "name": self.name,
            "priority": self.priority,
            "max_output": self.max_output,
            "min_output": self.min_output,
            "actual_output": self.actual_output,  # Rzeczywista wartość
            "setpoint_output": self.setpoint_output,  # NOWE: Wartość zadana
            "switch_status": self.switch_status,
            "device_status": self.device_status,
            "is_adjustable": self.is_adjustable,
            "pending_action": self.pending_action,
            "action_approved": self.action_approved,
        }

    def __str__(self):
        """Reprezentacja tekstowa obiektu."""
        status = "ON" if self.switch_status else "OFF"
        return (
            f"{self.name} (ID: {self.id}): "
            f"actual={self.actual_output:.2f} kW, "
            f"setpoint={self.setpoint_output:.2f} kW, "
            f"max={self.max_output:.2f} kW, "
            f"Status: {status}"
        )

    def __repr__(self):
        """Reprezentacja deweloperska obiektu."""
        return (
            f"EnergySource(id={self.id}, name='{self.name}', priority={self.priority}, "
            f"max_output={self.max_output}, min_output={self.min_output}, "
            f"actual_output={self.actual_output}, setpoint_output={self.setpoint_output}, "
            f"switch_status={self.switch_status}, device_status='{self.device_status}')"
        )