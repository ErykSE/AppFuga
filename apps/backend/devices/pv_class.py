from apps.backend.devices.energy_source_class import EnergySource


class PV(EnergySource):
    """
    Klasa dla urządzeń generującyh moc typu PV. Dziedziczy ona z klasy EnergySource.
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
            is_adjustable=True,
        )
