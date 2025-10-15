from apps.backend.devices.energy_point_class import EnergyPoint


class AdjustableDevice(EnergyPoint):
    """
    Klasa dla urządzeń/odbiorów, które można regulować w sposób zwiększania/zmniejszania zapotrzebowania.
    Dziedziczy z głównej klasy EnergyPoint.
    
    ZAKTUALIZOWANA: Dodano from_dict() i wsparcie dla nowych pól API.
    """

    def __init__(
        self,
        id,
        name,
        priority,
        power,
        switch_status,
        min_power,
        max_power,
        actual_output=None,  # NOWE
        setpoint_output=None,  # NOWE
        info_logger=None,  # NOWE
        error_logger=None,  # NOWE
    ):
        super().__init__(
            id=id,
            name=name,
            priority=priority,
            power=power,
            switch_status=switch_status,
            actual_output=actual_output,
            setpoint_output=setpoint_output,
            info_logger=info_logger,
            error_logger=error_logger,
        )
        self.min_power = min_power
        self.max_power = max_power

    @staticmethod
    def validate_data(data):
        """
        Waliduje dane urządzenia regulowanego.
        """
        if not EnergyPoint.validate_data(data):
            return False
        
        if "min_power" not in data or "max_power" not in data:
            print(f"Missing min_power or max_power in data: {data}")
            return False
        
        if not isinstance(data["min_power"], (int, float)) or data["min_power"] < 0:
            print(f"Invalid min_power: {data['min_power']}")
            return False
        
        if (
            not isinstance(data["max_power"], (int, float))
            or data["max_power"] <= data["min_power"]
        ):
            print(f"Invalid max_power: {data['max_power']}")
            return False
        
        if data["power"] < data["min_power"] or data["power"] > data["max_power"]:
            print(
                f"Power {data['power']} is outside of allowed range "
                f"[{data['min_power']}, {data['max_power']}]"
            )
            return False
        
        return True

    @classmethod
    def from_dict(cls, data, info_logger=None, error_logger=None):
        """
        NOWA METODA: Tworzy instancję AdjustableDevice ze słownika (z JSON API).
        
        Ta metoda jest KLUCZOWA - automatycznie mapuje dane z API!
        
        Args:
            data (dict): Słownik z danymi z API
            info_logger: Logger do informacji
            error_logger: Logger do błędów
            
        Returns:
            AdjustableDevice: Nowa instancja urządzenia
        """
        return cls(
            id=data.get("id"),
            name=data.get("name"),
            priority=data.get("priority", 15),  # Domyślny priorytet
            power=data.get("power", 0),
            switch_status=data.get("switch_status", True),
            min_power=data.get("min_power", 0),
            max_power=data.get("max_power", data.get("power", 0)),
            actual_output=data.get("actual_output"),
            setpoint_output=data.get("setpoint_output"),
            info_logger=info_logger,
            error_logger=error_logger
        )

    def set_power(self, new_power):
        """
        Ustawia nową moc urządzenia.
        ZAKTUALIZOWANA: ustawia setpoint_output, użyto loggerów.
        """
        if self.switch_status:
            # Ogranicz do zakresu
            if new_power < self.min_power:
                new_power = self.min_power
            elif new_power > self.max_power:
                new_power = self.max_power
            
            self.setpoint_output = new_power  # NOWE: ustaw setpoint
            # power pozostaje jako nominalna wartość
        else:
            self.setpoint_output = 0
        
        if self.info_logger:
            self.info_logger.info(f"{self.name} setpoint set to {self.setpoint_output:.2f} kW")
        else:
            print(f"{self.name} power set to {self.setpoint_output} kW")

    def increase_power(self, amount):
        """
        Zwiększa moc urządzenia o określoną wartość.
        ZAKTUALIZOWANA: operuje na setpoint_output.
        """
        current = self.setpoint_output if self.setpoint_output is not None else self.power
        new_power = min(current + amount, self.max_power)
        self.set_power(new_power)
        return new_power - current  # Zwraca faktycznie zwiększoną moc

    def decrease_power(self, amount):
        """
        Zmniejsza moc urządzenia o określoną wartość.
        ZAKTUALIZOWANA: operuje na setpoint_output, użyto loggerów.
        """
        current = self.setpoint_output if self.setpoint_output is not None else self.power
        old_power = current
        new_power = max(current - amount, self.min_power)
        self.setpoint_output = new_power  # NOWE: ustaw setpoint
        actual_reduction = old_power - new_power
        
        if self.info_logger:
            self.info_logger.info(
                f"{self.name} power decreased from {old_power:.2f} kW to {new_power:.2f} kW"
            )
        else:
            print(f"{self.name} power decreased from {old_power} kW to {new_power} kW")
        
        return actual_reduction

    def activate(self):
        """
        Aktywuje urządzenie z minimalną mocą.
        ZAKTUALIZOWANA: użyto loggerów.
        """
        super().activate()
        self.setpoint_output = self.min_power  # NOWE: ustaw setpoint na minimum
        
        if self.info_logger:
            self.info_logger.info(
                f"{self.name} activated with minimum power {self.min_power:.2f} kW"
            )
        else:
            print(f"{self.name} activated with minimum power {self.min_power} kW")

    def get_reducible_power(self):
        """
        Zwraca ilość mocy, którą można zredukować.
        ZAKTUALIZOWANA: używa setpoint_output.
        """
        current = self.setpoint_output if self.setpoint_output is not None else self.power
        return max(0, current - self.min_power)

    def to_dict(self):
        """
        Konwertuje obiekt do słownika (do zapisu JSON).
        ZAKTUALIZOWANA: dodano nowe pola.
        """
        base_dict = super().to_dict()
        base_dict.update({
            "min_power": self.min_power,
            "max_power": self.max_power
        })
        return base_dict

    def get_actual_output(self):
        """Zwraca rzeczywistą moc wyjściową."""
        if not self.switch_status:
            return 0
        return self.actual_output if self.actual_output is not None else self.power

    def get_max_output(self):
        """Zwraca maksymalną moc."""
        return self.max_power

    def __str__(self):
        """Reprezentacja tekstowa obiektu."""
        status = "ON" if self.switch_status else "OFF"
        return (
            f"{self.name} (ID: {self.id}): "
            f"power={self.get_current_power():.2f} kW "
            f"(range: {self.min_power:.2f}-{self.max_power:.2f} kW), "
            f"Status: {status}"
        )

    def __repr__(self):
        """Reprezentacja deweloperska obiektu."""
        return (
            f"AdjustableDevice(id={self.id}, name='{self.name}', "
            f"priority={self.priority}, power={self.power}, "
            f"min={self.min_power}, max={self.max_power}, "
            f"actual_output={self.actual_output}, "
            f"switch_status={self.switch_status})"
        )