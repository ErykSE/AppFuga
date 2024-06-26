from apps.backend.devices.energy_point_class import EnergyPoint


class NonAdjustableDevice(EnergyPoint):
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
