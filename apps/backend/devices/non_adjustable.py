from apps.backend.devices.energy_point_class import EnergyPoint


class NonAdjustableDevice(EnergyPoint):
    """
    Klasa dla urządzeń/odbiorów, których nie można regulować, jedyną opcją jset załączenie lub wyłączenie. Będzie ona dziedziczyć z głównej klasy EnergyPoint.
    """

    def __init__(
        self,
        id,
        name,
        priority,
        power,
        switch_status,
    ):
        super().__init__(
            id,
            name,
            priority,
            power,
            switch_status,
        )
