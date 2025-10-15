from apps.backend.devices.energy_source_class import EnergySource


class FuelCell(EnergySource):
    """
    Klasa dla urządzeń generujących moc typu Fuel Cell (ogniwo paliwowe).
    Dziedziczy z klasy EnergySource.
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
        setpoint_output=0,
        info_logger=None,
        error_logger=None,
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
            is_adjustable=True,  # Ogniwo paliwowe jest regulowane
            setpoint_output=setpoint_output,
            info_logger=info_logger,
            error_logger=error_logger,
        )

    @classmethod
    def from_dict(cls, data, info_logger=None, error_logger=None):
        """Tworzy instancję FuelCell ze słownika (z JSON API)."""
        return cls(
            id=data.get("id"),
            name=data.get("name"),
            priority=data.get("priority", 4),  # Domyślny priorytet 4
            max_output=data.get("max_output", 0),
            min_output=data.get("min_output", 0),
            actual_output=data.get("actual_output", 0),
            switch_status=data.get("switch_status", True),
            device_status=data.get("device_status", "offline"),
            setpoint_output=data.get("setpoint_output", 0),
            info_logger=info_logger,
            error_logger=error_logger
        )
