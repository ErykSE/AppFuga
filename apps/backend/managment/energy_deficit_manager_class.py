from apps.backend.managment.deficit_action import DeficitAction


class EnergyDeficitManager:
    def __init__(self, microgrid, osd):
        self.microgrid = microgrid
        self.osd = osd

    def handle_deficit(self, power_deficit):
        total_managed = 0
        remaining_deficit = power_deficit

        while remaining_deficit > 0:
            action = self.decide_deficit_action()
            result = self.execute_action(action, remaining_deficit)

            if result["success"]:
                total_managed += result["amount"]
                remaining_deficit -= result["amount"]
            else:
                break  # Nie możemy zarządzić więcej deficytem

        return {
            "amount_managed": total_managed,
            "remaining_deficit": remaining_deficit,
        }

    def decide_deficit_action(self):
        if not self.are_active_devices_at_full_capacity():
            return DeficitAction.INCREASE_ACTIVE_DEVICES
        elif self.are_inactive_devices_available():
            return DeficitAction.ACTIVATE_INACTIVE_DEVICES
        elif self.is_bess_available():
            return DeficitAction.DISCHARGE_BESS
        elif self.can_buy_energy():
            return DeficitAction.BUY_ENERGY
        else:
            return DeficitAction.LIMIT_CONSUMPTION

    def execute_action(self, action, deficit):
        if action == DeficitAction.INCREASE_ACTIVE_DEVICES:
            return self.increase_active_devices_output(deficit)
        elif action == DeficitAction.ACTIVATE_INACTIVE_DEVICES:
            return self.activate_inactive_devices(deficit)
        elif action == DeficitAction.DISCHARGE_BESS:
            return self.discharge_bess(deficit)
        elif action == DeficitAction.BUY_ENERGY:
            return self.buy_energy(deficit)
        else:  # DeficitAction.LIMIT_CONSUMPTION
            return self.limit_consumption(deficit)

    def are_active_devices_at_full_efficiency(self):
        return all(
            device.is_at_full_efficiency()
            for device in self.microgrid.get_active_devices()
        )

    def are_inactive_devices_available(self):
        return len(self.microgrid.get_inactive_devices()) > 0

    def is_bess_available(self):
        return any(
            bess.get_switch_status() and bess.get_charge_level() > 0
            for bess in self.microgrid.bess_units.devices
        )

    def can_buy_energy(self):
        return self.osd.get_contracted_import_possibility()

    def increase_active_devices_output(self, power_deficit):
        increased_power = 0
        for device in self.microgrid.get_active_devices():
            if not device.is_at_full_capacity():
                increase = device.increase_output_to_full_capacity()
                increased_power += increase
                if increased_power >= power_deficit:
                    break
        return {"success": increased_power > 0, "amount": increased_power}

    def activate_inactive_devices(self, power_deficit):
        activated_power = 0
        for device in self.microgrid.get_inactive_devices():
            if device.try_activate():
                activated_power += device.increase_output_to_full_capacity()
                if activated_power >= power_deficit:
                    break
        return {"success": activated_power > 0, "amount": activated_power}

    def discharge_bess(self, power_deficit):
        total_discharged = 0
        for bess in self.microgrid.bess_units:
            if bess.get_switch_status() and bess.get_charge_level() > 0:
                discharged = bess.discharge(
                    min(power_deficit - total_discharged, bess.get_charge_level())
                )
                total_discharged += discharged
                if total_discharged >= power_deficit:
                    break
        return {"success": total_discharged > 0, "amount": total_discharged}

    def buy_energy(self, power_deficit):
        if self.osd.get_bought_power() + power_deficit <= self.osd.get_purchase_limit():
            self.osd.buy_power(power_deficit)
            return {"success": True, "amount": power_deficit}
        else:
            remaining_power = (
                self.osd.get_purchase_limit() - self.osd.get_bought_power()
            )
            if remaining_power > 0:
                self.osd.buy_power(remaining_power)
                return {"success": True, "amount": remaining_power}
            else:
                return {"success": False, "amount": 0}

    def limit_consumption(self, power_deficit):
        limited_power = min(power_deficit, self.microgrid.get_total_consumption())
        self.microgrid.reduce_consumption(limited_power)
        return {"success": True, "amount": limited_power}
