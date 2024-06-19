from apps.backend.algorithms.set_device_class import DeviceSet


class Microgrid:
    def __init__(self):
        self.pv_panels = DeviceSet()
        self.wind_turbines = DeviceSet()
        self.fuel_turbines = DeviceSet()
        self.fuel_cells = DeviceSet()
        self.bess_units = DeviceSet()

    def add_pv_panel(self, pv_panel):
        self.pv_panels.add_device(pv_panel)

    def add_wind_turbine(self, wind_turbine):
        self.wind_turbines.add_device(wind_turbine)

    def add_fuel_turbine(self, fuel_turbine):
        self.fuel_turbines.add_device(fuel_turbine)

    def add_fuel_cell(self, fuel_cell):
        self.fuel_cells.add_device(fuel_cell)

    def add_bess(self, bess):
        self.bess_units.add_device(bess)


"""

# Przykład użycia
microgrid = Microgrid()
for i in range(5):
    microgrid.add_pv_panel(PVPanel(f"PV Panel {i+1}"))

for i in range(3):
    microgrid.add_wind_turbine(WindTurbine(f"Wind Turbine {i+1}"))

for i in range(2):
    microgrid.add_bess(BESS(f"BESS {i+1}"))

"""
