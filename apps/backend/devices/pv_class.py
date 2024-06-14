from apps.backend.devices.energy_class import EnergySource


class PV(EnergySource):
    def __init__(self, power, efficiency, sunlight, regulator_setting=50):
        super().__init__(power)
        self.efficiency = efficiency  # Efficiency of PV panels
        self.sunlight = sunlight  # Current sunlight exposure in %
        self.regulator_setting = regulator_setting  # Regulator setting in %

    def get_current_power(self):
        self.power = self.power * (self.efficiency / 100) * (self.sunlight / 100)
        return self.power

    def adjust_regulator(self, target_power):
        max_regulator_value = 100
        if self.power > target_power:
            reduction = self.power - target_power
            self.regulator_setting -= (reduction / self.power) * max_regulator_value
            self.regulator_setting = max(0, self.regulator_setting)
        else:
            self.regulator_setting = max_regulator_value
        self.power = self.power * (self.regulator_setting / max_regulator_value)
        return self.power
