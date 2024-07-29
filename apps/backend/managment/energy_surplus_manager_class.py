from apps.backend.managment.surplus_action import SurplusAction


class EnergySurplusManager:
    """
    Klasa zarządzająca nadwyżką energii.
    """

    def __init__(self, microgrid, osd, info_logger, error_logger):
        self.microgrid = microgrid
        self.osd = osd
        self.info_logger = info_logger
        self.error_logger = error_logger
        self.previous_decision = True  # Domyślnie priorytet ładowania

    def manage_surplus_energy(self, power_surplus):
        total_managed = 0
        remaining_surplus = power_surplus
        iteration = 0
        MAX_ITERATIONS = 100

        try:
            while remaining_surplus > 0 and iteration < MAX_ITERATIONS:
                iteration += 1
                self.info_logger.info(
                    f"Iteration {iteration}, surplus remaining: {remaining_surplus} kW"
                )

                bess_available = self.check_bess_availability()
                export_possible = self.is_export_possible()

                # Określamy dostępne akcje
                available_actions = []
                if bess_available and export_possible:
                    available_actions.append(SurplusAction.BOTH)
                if bess_available:
                    available_actions.append(SurplusAction.CHARGE_BATTERY)
                if export_possible:
                    available_actions.append(SurplusAction.SELL_ENERGY)
                available_actions.append(SurplusAction.LIMIT_GENERATION)

                # Próbujemy każdą dostępną akcję
                for action in available_actions:
                    self.info_logger.info(f"Attempting to perform the action: {action}")
                    result = self.execute_action(action, remaining_surplus)

                    if result["success"]:
                        total_managed += result["amount"]
                        remaining_surplus -= result["amount"]
                        self.info_logger.info(
                            f"Action {action} managed {result['amount']} kW. Surplus remaining: {remaining_surplus} kW"
                        )
                        break  # Przerwij pętlę for, jeśli akcja się powiodła
                    else:
                        self.info_logger.info(
                            f"Action {action} has failed. Reason: {result.get('reason', 'Unknown')}"
                        )

                # Jeśli żadna akcja nie powiodła się, przerwij główną pętlę
                else:
                    self.error_logger.error(
                        "No action successful. Interruption of surplus management."
                    )
                    break

            if iteration == MAX_ITERATIONS:
                self.error_logger.error(
                    f"The maximum number of iterations ({MAX_ITERATIONS}) has been reached without solving the surplus."
                )

        except Exception as e:
            self.error_logger.error(f"Error in manage_surplus_energy: {str(e)}")

        return {
            "amount_managed": total_managed,
            "remaining_surplus": remaining_surplus,
        }

    def execute_action(self, action, remaining_surplus):
        if action == SurplusAction.BOTH:
            self.info_logger.info("BOTH")
            return self.handle_both_action(remaining_surplus)
        elif action == SurplusAction.CHARGE_BATTERY:
            self.info_logger.info("CHARGE")
            return self.decide_to_charge_bess(remaining_surplus)
        elif action == SurplusAction.SELL_ENERGY:
            self.info_logger.info("SELL")
            return self.decide_to_sell_energy(remaining_surplus)
        elif action == SurplusAction.LIMIT_GENERATION:
            self.info_logger.info("LIMIT")
            return self.limit_energy_generation(remaining_surplus)
        else:
            return {"success": False, "amount": 0, "reason": "Nieznana akcja"}

    def should_prioritize_charging_or_selling(
        self, surplus_power, battery_free_percentage, current_selling_price
    ):
        # Parametry do konfiguracji
        MIN_SELLING_PRICE = 0.10
        MAX_SELLING_PRICE = 0.25
        BATTERY_THRESHOLD = 20
        PRICE_THRESHOLD = 0.7
        HYSTERESIS = 0.05

        if battery_free_percentage <= BATTERY_THRESHOLD:
            print(f"Charging priority: low battery ({100 - battery_free_percentage}%)")
            return True

        if battery_free_percentage == 0:
            print("BESS full, sales priority")
            return False

        price_factor = (current_selling_price - MIN_SELLING_PRICE) / (
            MAX_SELLING_PRICE - MIN_SELLING_PRICE
        )
        price_factor = max(0, min(price_factor, 1))

        battery_factor = 1 - (battery_free_percentage / 100)

        if price_factor > PRICE_THRESHOLD and surplus_power > 50:
            print(
                f"Sales priority: high price ({current_selling_price}) and significant surplus ({surplus_power} kW)"
            )
            return False
        elif battery_factor > price_factor + HYSTERESIS:
            print(
                f"Charging priority: battery factor ({battery_factor:.2f}) > price factor ({price_factor:.2f})"
            )
            return True
        elif price_factor > battery_factor + HYSTERESIS:
            print(
                f"Sales priority: price factor ({price_factor:.2f}) > battery factor ({battery_factor:.2f})"
            )
            return False
        else:
            print(f"Maintaining the previous decision: values ​​in the hysteresis range")
            return self.previous_decision

    def get_bess_free_capacity(self):
        try:
            if self.microgrid.bess:
                return max(
                    self.microgrid.bess.get_capacity()
                    - self.microgrid.bess.get_charge_level(),
                    0,
                )
            return 0
        except Exception as e:
            self.error_logger.error(
                f"Error in attempt to calculate available space in a numerical value: {str(e)}"
            )

    def get_bess_free_percentage(self):
        try:
            if self.microgrid.bess and self.microgrid.bess.get_capacity() > 0:
                return (
                    self.get_bess_free_capacity() / self.microgrid.bess.get_capacity()
                ) * 100
            return 0
        except Exception as e:
            self.error_logger.error(
                f"Error in attempting to calculate the available space in the %: {str(e)}"
            )

    def decide_to_charge_bess(self, power_surplus):
        try:
            if not self.check_bess_availability():
                self.info_logger.info("BESS is not available for charging.")
                return {"success": False, "amount": 0, "reason": "BESS not available"}

            bess = self.microgrid.bess
            free_capacity = self.get_bess_free_capacity()

            if free_capacity == 0:
                self.info_logger.info("BESS is fully charged. No capacity available.")
                return {"success": False, "amount": 0, "reason": "BESS full"}

            amount_to_charge = min(power_surplus, free_capacity)
            percent_to_charge = (amount_to_charge / bess.get_capacity()) * 100
            charged_percent, actual_charge = bess.try_charge(percent_to_charge)

            self.info_logger.info(f"Successfully charged BESS o {actual_charge} kW.")
            return {"success": True, "amount": actual_charge}
        except Exception as e:
            self.error_logger.error(f"Error in decide_to_charge_bess: {str(e)}")
            return {"success": False, "amount": 0, "reason": str(e)}

    def decide_to_sell_energy(self, power_surplus):
        try:
            if not self.is_export_possible():
                return {"success": False, "amount": 0, "reason": "Export impossible"}

            sale_limit = self.osd.get_sale_limit()
            sold_power = self.osd.get_sold_power()
            remaining_sale_capacity = sale_limit - sold_power

            if remaining_sale_capacity <= 0:
                self.info_logger.info(
                    "The sales limit has been reached. No more energy can be sold."
                )
                return {
                    "success": False,
                    "amount": 0,
                    "reason": "Sales limit reached",
                }

            amount_to_sell = min(power_surplus, remaining_sale_capacity)

            if amount_to_sell > 0:
                sold_amount = self.sell_energy(amount_to_sell)
                return {"success": True, "amount": sold_amount}
            else:
                return {
                    "success": False,
                    "amount": 0,
                    "reason": "No possibility of sale",
                }
        except Exception as e:
            self.error_logger.error(f"Error in decide_to_sell_energy: {str(e)}")
            return {"success": False, "amount": 0, "reason": str(e)}

    def handle_both_action(self, remaining_surplus):
        battery_free_percentage = self.get_bess_free_percentage()
        current_selling_price = self.osd.current_tariff_sell

        should_charge = self.should_prioritize_charging_or_selling(
            remaining_surplus,
            battery_free_percentage,
            current_selling_price,
        )

        if should_charge:
            result = self.decide_to_charge_bess(remaining_surplus)
            if not result["success"] or result["amount"] < remaining_surplus:
                sell_result = self.decide_to_sell_energy(
                    remaining_surplus - result["amount"]
                )
                result["amount"] += sell_result["amount"]
                result["success"] = result["success"] or sell_result["success"]
        else:
            result = self.decide_to_sell_energy(remaining_surplus)
            if not result["success"] or result["amount"] < remaining_surplus:
                charge_result = self.decide_to_charge_bess(
                    remaining_surplus - result["amount"]
                )
                result["amount"] += charge_result["amount"]
                result["success"] = result["success"] or charge_result["success"]

        return result

    def sell_energy(self, power_surplus):
        try:
            self.osd.sell_power(power_surplus)
            self.info_logger.info(
                f"Selling {power_surplus} kW of surplus energy. Total energy sold: {self.osd.get_sold_power()} kW."
            )
            return power_surplus
        except Exception as e:
            self.error_logger.error(f"Error in sell_energy: {str(e)}")
            return 0

    def limit_energy_generation(self, power_surplus):
        self.info_logger.info(
            f"Attempting to limit energy generation by {power_surplus} kW"
        )
        total_reduced = 0

        # Sortuj urządzenia według priorytetu (rosnąco)
        active_generators = sorted(
            [
                device
                for device in self.microgrid.get_all_devices()
                if device.get_switch_status()
            ],
            key=lambda x: x.priority,
        )

        for device in active_generators:
            if total_reduced >= power_surplus:
                break

            current_output = device.get_actual_output()
            min_output = device.get_min_output()
            reducible_power = current_output - min_output

            reduction = min(reducible_power, power_surplus - total_reduced)

            if reduction > 0:
                new_output = current_output - reduction
                device.set_output(new_output)
                actual_reduction = current_output - device.get_actual_output()
                total_reduced += actual_reduction
                self.info_logger.info(
                    f"Reduced {device.name} (priority: {device.priority}) power by {actual_reduction} kW from {current_output} kW to {device.get_actual_output()} kW"
                )

        remaining_surplus = power_surplus - total_reduced
        self.info_logger.info(f"Total power generation reduced: {total_reduced} kW")
        self.info_logger.info(f"Remaining surplus: {remaining_surplus} kW")

        return {
            "success": total_reduced > 0,
            "amount": total_reduced,
            "remaining_surplus": remaining_surplus,
        }

    def is_export_possible(self):
        try:
            return self.osd.get_contracted_export_possibility()
        except Exception as e:
            self.error_logger.error(f"Error checking export possibility: {str(e)}")
            return False

    def check_bess_availability(self):
        try:
            return self.microgrid.bess.get_switch_status()
        except Exception as e:
            self.error_logger.error(f"Error checking bess possibility: {str(e)}")
            return False
