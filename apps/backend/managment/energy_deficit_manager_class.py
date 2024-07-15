class EnergyDeficitManager:
    def __init__(self, microgrid, osd):
        self.microgrid = microgrid
        self.osd = osd

    def handle_power_deficit(self, power_deficit):
        if not self.activate_inactive_devices():
            if not self.are_active_devices_running_at_full_capacity():
                self.increase_active_device_output()
            else:
                if self.is_bess_available():
                    self.decide_bess_action(power_deficit)
                else:
                    self.import_energy_from_supplier(power_deficit)

    def activate_inactive_devices(self):
        for device in self.microgrid.get_all_devices():
            if not device.is_active():
                device.activate()
                return True
        return False

    def are_active_devices_running_at_full_capacity(self):
        for device in self.microgrid.get_all_devices():
            if device.is_active() and not device.is_running_at_full_capacity():
                return False
        return True

    def increase_active_device_output(self):
        for device in self.microgrid.get_all_devices():
            if device.is_active():
                device.increase_output_to_full_capacity()

    def is_bess_available(self):
        for bess in self.microgrid.bess_units.devices:
            if bess.get_switch_status():
                return True
        return False

    def decide_bess_action(self, power_deficit):
        if self.should_charge_bess():
            self.charge_bess(power_deficit)
        else:
            self.import_energy_from_supplier(power_deficit)

    def should_charge_bess(self):
        # logic to determine whether to charge BESS or import energy
        pass

    def charge_bess(self, power_deficit):
        for bess in self.microgrid.bess_units.devices:
            if bess.get_switch_status():
                bess.charge(power_deficit)
                return

    def import_energy_from_supplier(self, power_deficit):
        # logic to import energy from supplier
        pass

    def disconnect_consumers(self):
        # logic to disconnect consumers when import exceeds contract limit
        pass
