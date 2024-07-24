from apps.backend.devices.energy_source_class import EnergySource


class FuelCell(EnergySource):
    """
    Klasa dla urządzeń generującyh moc typu FuellCell. Dziedziczy ona z klasy EnergySource.
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
    ):
        super().__init__(
            id,
            name,
            priority,
            max_output,
            min_output,
            actual_output,
            switch_status,
            device_status,
        )
