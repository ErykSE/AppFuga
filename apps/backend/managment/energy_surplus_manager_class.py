class EnergySurplusManager:
    def __init__(self, microgrid, osd, contract):
        self.microgrid = microgrid
        self.osd = osd
        self.contract = contract
        self.currently_charging_bess_index = 0

    def handle_surplus(self, power_surplus):
        if self.is_export_possible():
            self.decide_to_sell_energy(power_surplus)
        else:
            self.limit_generated_power(power_surplus)

    def is_export_possible(self):
        return self.contract.get_is_export_possible()

    def decide_to_sell_energy(self, power_surplus):
        if self.should_sell_energy():
            if self.check_sale_limit(power_surplus):
                self.sell_energy(power_surplus)
            else:
                remaining_power = self.get_remaining_sale_power()
                self.sell_energy(remaining_power)
                self.handle_surplus_without_selling(power_surplus - remaining_power)
        else:
            self.handle_surplus_without_selling(power_surplus)

    def should_sell_energy(self):
        # Placeholder for tariff check logic
        pass

    def check_sale_limit(self, power_surplus):
        sale_limit = self.contract.get_sale_limit()
        if self.osd.get_sold_power() + power_surplus > sale_limit:
            return False
        return True

    def get_remaining_sale_power(self):
        sale_limit = self.contract.get_sale_limit()
        remaining_power = sale_limit - self.osd.get_sold_power()
        return remaining_power

    def sell_energy(self, power_surplus):
        print(
            f"Selling {power_surplus} kW of surplus energy. Total energy sold: {self.osd.get_sold_power()} kW."
        )

    def handle_surplus_without_selling(self, power_surplus):
        if self.check_bess_availability():
            if self.check_bess_charge():
                self.handle_charged_bess(power_surplus)
            else:
                self.charge_bess(
                    power_surplus, attempts=3, delay=1, target_charge_level=80
                )
        else:
            self.limit_generated_power(power_surplus)

    def check_bess_availability(self):
        for bess in self.microgrid.bess_units.devices:
            if bess.is_switch_closed():
                return True
        return False

    def check_bess_charge(self):
        for bess in self.microgrid.bess_units.devices:
            if bess.is_charged():
                return True
        return False

    def handle_charged_bess(self, power_surplus):
        pass
        # to wróć do pytania o decyzję dotyczącą sprzedania z flagą, że muszę rozważyć sprzedaż, bo bess są naładowane

    def charge_bess(self, power_surplus, attempts, delay, target_charge_level):
        for _ in range(attempts):
            if self.currently_charging_bess_index >= len(
                self.microgrid.bess_units.devices
            ):
                self.currently_charging_bess_index = 0
            bess = self.microgrid.bess_units.devices[self.currently_charging_bess_index]
            if bess.charge(power_surplus, attempts, delay, target_charge_level):
                self.currently_charging_bess_index += 1
                break
            else:
                self.currently_charging_bess_index += 1
        else:
            print(f"Failed to charge any BESS after {attempts} attempts.")

    def limit_generated_power(self, power_surplus):
        pass  # Placeholder for future logic
