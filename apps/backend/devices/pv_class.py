from apps.backend.devices.energy_source_class import EnergySource


class PV(EnergySource):
    """
    Klasa dla urządzeń generujących moc typu PV (panele fotowoltaiczne).
    Dziedziczy z klasy EnergySource.
    
    ZAKTUALIZOWANA: Dodano wsparcie dla nowych pól API (setpoint_output, loggery).
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
        setpoint_output=0,  # NOWE
        info_logger=None,  # NOWE
        error_logger=None,  # NOWE
    ):
        super().__init__(
            id=id,
            name=name,
            priority=priority,
            max_output=max_output,
            min_output=min_output,
            actual_output=actual_output,
            switch_status=switch_status,
            device_status=device_status,
            is_adjustable=True,  # PV jest regulowane
            setpoint_output=setpoint_output,  # NOWE
            info_logger=info_logger,  # NOWE
            error_logger=error_logger,  # NOWE
        )

    @classmethod
    def from_dict(cls, data, info_logger=None, error_logger=None):
        """
        NOWA METODA: Tworzy instancję PV ze słownika (z JSON API).
        """
        return cls(
            id=data.get("id"),
            name=data.get("name"),
            priority=data.get("priority", 1),  # PV ma domyślnie priorytet 1
            max_output=data.get("max_output", 0),
            min_output=data.get("min_output", 0),
            actual_output=data.get("actual_output", 0),
            switch_status=data.get("switch_status", True),
            device_status=data.get("device_status", "offline"),
            setpoint_output=data.get("setpoint_output", 0),
            info_logger=info_logger,
            error_logger=error_logger
        )