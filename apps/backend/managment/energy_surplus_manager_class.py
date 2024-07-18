import logging
from apps.backend.managment.surplus_action import SurplusAction


class EnergySurplusManager:
    def __init__(self, microgrid, osd):
        self.microgrid = microgrid
        self.osd = osd
        self.currently_charging_bess_index = 0
        self.logger = logging.getLogger(__name__)

    def handle_surplus(self):

        bess_available = self.check_bess_availability()
        export_possible = self.is_export_possible()
        print(f"BESS available: {bess_available}, Export possible: {export_possible}")

        if self.check_bess_availability() and self.is_export_possible():
            print("BOTH")
            return SurplusAction.BOTH
        elif self.check_bess_availability():
            print("Charge")
            return SurplusAction.CHARGE_BATTERY
        elif self.is_export_possible():
            print("Sell")
            return SurplusAction.SELL_ENERGY
        else:
            print("Limit")
            return SurplusAction.LIMIT_GENERATION

    def manage_surplus_energy(self, power_surplus):
        total_managed = 0
        remaining_surplus = power_surplus

        while remaining_surplus > 0:
            action = self.handle_surplus()
            result = {"success": False, "amount": 0}

            if action == SurplusAction.BOTH:
                if self.should_prioritize_charging_or_selling():
                    # Priorytet dla ładowania baterii
                    bess_result = self.decide_to_charge_bess(remaining_surplus)
                    remaining_surplus -= bess_result["amount"]
                    if remaining_surplus > 0:
                        sell_result = self.decide_to_sell_energy(remaining_surplus)
                        remaining_surplus -= sell_result["amount"]
                    result["amount"] = bess_result["amount"] + sell_result["amount"]
                    result["success"] = bess_result["success"] or sell_result["success"]
                else:
                    # Priorytet dla sprzedaży energii
                    sell_result = self.decide_to_sell_energy(remaining_surplus)
                    remaining_surplus -= sell_result["amount"]
                    if remaining_surplus > 0:
                        bess_result = self.decide_to_charge_bess(remaining_surplus)
                        remaining_surplus -= bess_result["amount"]
                    result["amount"] = sell_result["amount"] + bess_result["amount"]
                    result["success"] = sell_result["success"] or bess_result["success"]
            elif action == SurplusAction.CHARGE_BATTERY:
                result = self.decide_to_charge_bess(remaining_surplus)
                remaining_surplus -= result["amount"]
            elif action == SurplusAction.SELL_ENERGY:
                result = self.decide_to_sell_energy(remaining_surplus)
                remaining_surplus -= result["amount"]
            else:  # SurplusAction.LIMIT_GENERATION
                result = self.limit_energy_generation(remaining_surplus)
                remaining_surplus -= result["amount"]

            total_managed += result["amount"]

            if not result["success"]:
                break  # Jeśli nie udało się zarządzić nadwyżką, przerwij pętlę

        return {
            "action": action,
            "amount_managed": total_managed,
            "remaining_surplus": remaining_surplus,
        }

    def should_prioritize_charging_or_selling(self):
        # Implementacja logiki decyzyjnej
        return True

    def decide_to_charge_bess(self, power_surplus):
        # Implementacja z dodatkowym sprawdzeniem dostępności BESS
        if not self.check_bess_availability():
            return {"success": False, "amount": 0}

        chargeable_bess = [bess for bess in self.microgrid.bess if bess.is_uncharged()]
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
        # Implementacja z dodatkowym sprawdzeniem możliwości eksportu
        if not self.is_export_possible():
            return {"success": False, "amount": 0}
        # Reszta implementacji bez zmian

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
        # Tu logika ograniczania generacji
        return {"success": True, "amount": power_surplus}

    def is_export_possible(self):
        return self.osd.get_contracted_export_possibility()

    def check_sale_limit(self, power_surplus):
        sale_limit = self.osd.get_sale_limit()
        return self.osd.get_sold_power() + power_surplus <= sale_limit

    def check_bess_availability(self):
        print(f"Checking BESS availability. BESS units: {self.microgrid.bess}")
        for bess in self.microgrid.bess:
            print(f"BESS {bess.id} switch status: {bess.get_switch_status()}")
            if bess.get_switch_status():
                return True
        return False

    def get_remaining_sale_power(self):
        sale_limit = self.osd.get_contracted_sale_limit()
        return sale_limit - self.osd.get_sold_power()

    def get_remaining_bess_power(self):
        return sum(
            bess.get_capacity() - bess.get_charge_level()
            for bess in self.microgrid.bess
        )
