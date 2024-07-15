import logging
from apps.backend.managment.surplus_action import SurplusAction


class EnergySurplusManager:
    def __init__(self, microgrid, osd):
        self.microgrid = microgrid
        self.osd = osd
        self.currently_charging_bess_index = 0
        self.logger = logging.getLogger(__name__)

    def handle_surplus(self):
        if self.check_bess_availability() and self.is_export_possible():
            return SurplusAction.BOTH
        elif self.check_bess_availability():
            return SurplusAction.CHARGE_BATTERY
        elif self.is_export_possible():
            return SurplusAction.SELL_ENERGY
        else:
            return SurplusAction.LIMIT_GENERATION

    def manage_surplus_energy(self, power_surplus):
        total_managed = 0
        action = self.handle_surplus()

        if action == SurplusAction.BOTH:
            if self.should_prioritize_charging_or_selling():
                result = self.decide_to_sell_energy(power_surplus)
                if not result["success"]:
                    result = self.decide_to_charge_bess(power_surplus)
            else:
                result = self.decide_to_charge_bess(power_surplus)
                if not result["success"]:
                    result = self.decide_to_sell_energy(power_surplus)
        elif action == SurplusAction.CHARGE_BATTERY:
            result = self.decide_to_charge_bess(power_surplus)
        elif action == SurplusAction.SELL_ENERGY:
            result = self.decide_to_sell_energy(power_surplus)
        else:  # SurplusAction.LIMIT_GENERATION
            result = self.limit_energy_generation(power_surplus)

        total_managed += result["amount"]

        return {
            "action": action,
            "amount_managed": total_managed,
            "remaining_surplus": power_surplus - total_managed,
        }

    def should_prioritize_charging_or_selling(self):
        # Implementacja logiki decyzyjnej
        return True

    def decide_to_charge_bess(self, power_surplus):
        chargeable_bess = [
            bess for bess in self.microgrid.bess_units.devices if bess.is_uncharged()
        ]
        if not chargeable_bess:
            return {"success": False, "amount": 0}

        total_chargeable_capacity = sum(
            bess.get_capacity() - bess.get_charge_level() for bess in chargeable_bess
        )
        amount_charged = self.charge_bess(
            chargeable_bess, min(power_surplus, total_chargeable_capacity)
        )
        return {"success": True, "amount": amount_charged}

    def charge_bess(self, chargeable_bess, power_to_charge):
        power_charged = 0
        for bess in chargeable_bess:
            max_charge = bess.get_capacity() - bess.get_charge_level()
            charge_amount = min(power_to_charge - power_charged, max_charge)
            if bess.get_capacity() > 0:
                percent_to_charge = (charge_amount / bess.get_capacity()) * 100
                charged_percent, actual_charge = bess.try_charge(percent_to_charge)
                power_charged += actual_charge
                if power_charged >= power_to_charge:
                    break
            else:
                self.logger.warning(f"BESS {bess.id} has zero capacity")
        return power_charged

    def decide_to_sell_energy(self, power_surplus):
        if self.check_sale_limit(power_surplus):
            amount_sold = self.sell_energy(power_surplus)
            return {"success": True, "amount": amount_sold}
        else:
            remaining_power = self.get_remaining_sale_power()
            if remaining_power > 0:
                amount_sold = self.sell_energy(remaining_power)
                return {"success": True, "amount": amount_sold}
            else:
                return {"success": False, "amount": 0}

    def sell_energy(self, power_surplus):
        self.osd.sell_power(power_surplus)
        print(
            f"Selling {power_surplus} kW of surplus energy. Total energy sold: {self.osd.get_sold_power()} kW."
        )
        return power_surplus

    def limit_energy_generation(self, power_surplus):
        print(f"Limiting {power_surplus} kW of generated power.")
        # Tu możesz dodać logikę ograniczania generacji
        return {"success": True, "amount": power_surplus}

    def is_export_possible(self):
        return self.osd.get_contracted_export_possibility()

    def check_sale_limit(self, power_surplus):
        sale_limit = self.osd.get_sale_limit()
        return self.osd.get_sold_power() + power_surplus <= sale_limit

    def check_bess_availability(self):
        for bess in self.microgrid.bess_units.devices:
            if bess.get_switch_status():
                return True
        return False

    def get_remaining_sale_power(self):
        sale_limit = self.osd.get_contracted_sale_limit()
        return sale_limit - self.osd.get_sold_power()

    def get_remaining_bess_power(self):
        return sum(
            bess.get_capacity() - bess.get_charge_level()
            for bess in self.microgrid.bess_units.devices
        )


"""

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

        """
