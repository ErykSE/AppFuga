from apps.backend.devices.energy_class import EnergySource


class PV(EnergySource):
    def __init__(
        self,
        id,
        name,
        max_output,
        current_output=0,
        switch_status=False,
        status="offline",
    ):
        super().__init__(id, name, max_output, current_output, switch_status, status)
