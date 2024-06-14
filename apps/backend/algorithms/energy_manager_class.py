class EnergyManager:
    def __init__(self, pv, bess, osd):
        self.pv = pv
        self.bess = bess
        self.osd = osd
        self.moc_zakontraktowana = 1.0  # Example value in kW
        self.margin = 0.02  # Example margin

    def manage_export(self):
        if self.is_export_possible():
            if not self.bess.is_charged():
                self.bess.charge()
            else:
                self.export_energy()
        else:
            self.reduce_generation()

    def manage_import(self):
        if not self.bess.is_charged():
            self.bess.charge()
        else:
            self.bess.discharge()

        if self.osd.get_current_power() > self.pv.get_current_power():
            self.activate_loads()

    def is_export_possible(self):
        return True

    def export_energy(self):
        print("Exporting energy to OSD")

    def reduce_generation(self):
        moc_generowana = self.pv.get_current_power()
        moc_przekroczenia = moc_generowana - (
            self.moc_zakontraktowana * (1 + self.margin)
        )

        if moc_przekroczenia > 0:
            self.pv.adjust_regulator(moc_generowana - moc_przekroczenia)
        else:
            self.pv.adjust_regulator(moc_generowana)

        print(
            f"Reducing power generation, current PV power: {self.pv.get_current_power()} kW"
        )

    def activate_loads(self):
        print("Activating additional loads")
