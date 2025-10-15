from apps.backend.devices.energy_point_class import EnergyPoint


class NonAdjustableDevice(EnergyPoint):
    """
    Klasa dla urządzeń/odbiorów, których nie można regulować.
    Jedyną opcją jest załączenie lub wyłączenie.
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
        actual_output=None,  # NOWE: rzeczywista wartość z SCADA
        setpoint_output=None,  # NOWE: wartość zadana
        info_logger=None,  # NOWE: logger
        error_logger=None,  # NOWE: logger
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

    @classmethod
    def from_dict(cls, data, info_logger=None, error_logger=None):
        """
        NOWA METODA: Tworzy instancję NonAdjustableDevice ze słownika (z JSON API).
        
        Args:
            data (dict): Słownik z danymi z API
            info_logger: Logger do informacji
            error_logger: Logger do błędów
            
        Returns:
            NonAdjustableDevice: Nowa instancja urządzenia
        """
        return cls(
            id=data.get("id"),
            name=data.get("name"),
            priority=data.get("priority", 11),  # Domyślny priorytet dla non-adjustable
            power=data.get("power", 0),
            switch_status=data.get("switch_status", True),
            actual_output=data.get("actual_output"),
            setpoint_output=data.get("setpoint_output"),
            info_logger=info_logger,
            error_logger=error_logger
        )

    def __str__(self):
        """Reprezentacja tekstowa obiektu."""
        status = "ON" if self.switch_status else "OFF"
        return (
            f"{self.name} (ID: {self.id}): "
            f"power={self.get_current_power():.2f} kW "
            f"(non-adjustable), "
            f"Status: {status}"
        )

    def __repr__(self):
        """Reprezentacja deweloperska obiektu."""
        return (
            f"NonAdjustableDevice(id={self.id}, name='{self.name}', "
            f"priority={self.priority}, power={self.power}, "
            f"actual_output={self.actual_output}, "
            f"switch_status={self.switch_status})"
        )