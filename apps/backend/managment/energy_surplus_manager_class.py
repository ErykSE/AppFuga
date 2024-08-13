from apps.backend.managment.surplus_action import SurplusAction


class EnergySurplusManager:
    """
    Klasa odpowiedzialna za zarządzanie nadwyżką energii w systemie mikrosieci.

    Ta klasa implementuje różne strategie obsługi nadwyżki produkcji energii,
    w tym ładowanie BESS, sprzedaż energii do sieci i ograniczanie
    generacji energii. Priorytetyzuje działania w oparciu o aktualny stan systemu,
    poziom naładowania BESS i ceny energii.

    Atrybuty:
        microgrid (Microgrid): Zarządzany system mikrosieci.
        osd (OSD): Obiekt zawierający dane dotyczące informacji kontraktowych pomiędzy przedsiębiorstwem, a dostawcą.
        info_logger (Logger): Logger do wiadomości informacyjnych.
        error_logger (Logger): Logger do wiadomości o błędach.
        previous_decision (bool): Flaga przechowująca poprzednią decyzję dla histerezy.
    """

    def __init__(self, microgrid, osd, info_logger, error_logger, execute_action_func):
        self.microgrid = microgrid
        self.osd = osd
        self.info_logger = info_logger
        self.error_logger = error_logger
        self.execute_action_func = execute_action_func
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
                    self.info_logger.info(f"Action type: {type(action)}")
                    result = self.execute_action(action, remaining_surplus)
                    self.info_logger.info(f"Action result: {result}")

                    if result["success"]:
                        total_managed += result["amount"]
                        remaining_surplus -= result["amount"]
                        self.info_logger.info(
                            f"Action {action} managed {result['amount']} kW. Surplus remaining: {remaining_surplus} kW"
                        )
                        break
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
            self.error_logger.exception("Full traceback:")

        return {
            "amount_managed": total_managed,
            "remaining_surplus": remaining_surplus,
        }

    def execute_action(self, action, remaining_surplus):
        """
        Wykonuje określone działanie w celu zarządzania nadwyżką energii.

        Argumenty:
            action (SurplusAction): Działanie do wykonania.
            remaining_surplus (float): Pozostała nadwyżka energii do zarządzania w kW.

        Zwraca:
            dict: Słownik wskazujący na sukces działania i ilość zarządzonej energii.
        """
        self.info_logger.info(f"Executing action: {action}, type: {type(action)}")
        self.info_logger.info(f"Remaining surplus: {remaining_surplus}")

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
            return {"success": False, "amount": 0, "reason": "Unknown action"}

    def should_prioritize_charging_or_selling(
        self, surplus_power, battery_free_percentage, current_selling_price
    ):
        """
        Określa, czy priorytetem powinno być ładowanie BESS czy sprzedaż energii.

        Ta metoda wykorzystuje różne czynniki, takie jak poziom naładowania BESS,
        aktualna cena sprzedaży i nadwyżka mocy, aby zdecydować o priorytecie między
        ładowaniem, a sprzedażą energii do sieci.

        Argumenty:
            surplus_power (float): Aktualna nadwyżka mocy w kW.
            battery_free_percentage (float): Procent wolnej pojemności w BESS.
            current_selling_price (float): Aktualna cena sprzedaży energii do sieci.

        Zwraca:
            bool: True jeśli priorytetem powinno być ładowanie, False jeśli sprzedaż.
        """
        # Parametry do konfiguracji
        MIN_SELLING_PRICE = 0.10
        MAX_SELLING_PRICE = 0.25
        BATTERY_THRESHOLD = 20
        PRICE_THRESHOLD = 0.7
        HYSTERESIS = 0.05

        if battery_free_percentage <= BATTERY_THRESHOLD:
            return True

        if battery_free_percentage == 0:
            return False

        price_factor = (current_selling_price - MIN_SELLING_PRICE) / (
            MAX_SELLING_PRICE - MIN_SELLING_PRICE
        )
        price_factor = max(0, min(price_factor, 1))

        battery_factor = 1 - (battery_free_percentage / 100)

        if price_factor > PRICE_THRESHOLD and surplus_power > 50:
            self.info_logger.info(
                f"Sales priority: high price ({current_selling_price}) and significant surplus ({surplus_power} kW)"
            )

            return False
        elif battery_factor > price_factor + HYSTERESIS:
            self.info_logger.info(
                f"Charging priority: battery factor ({battery_factor:.2f}) > price factor ({price_factor:.2f})"
            )

            return True
        elif price_factor > battery_factor + HYSTERESIS:
            self.info_logger.info(
                f"Sales priority: price factor ({price_factor:.2f}) > battery factor ({battery_factor:.2f})"
            )

            return False
        else:
            self.info_logger.info(
                f"Maintaining the previous decision: values ​​in the hysteresis range"
            )

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
        """
        Decyduje, czy ładować system BESS i o ile.

        Ta metoda sprawdza dostępność i pojemność BESS, a następnie próbuje
        naładować go nadwyżką energii, jeśli to możliwe.

        Argumenty:
            power_surplus (float): Ilość nadwyżki energii dostępnej do ładowania w kW.

        Zwraca:
            dict: Słownik wskazujący na sukces próby ładowania i naładowaną ilość.
        """
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
        """
        Decyduje, czy sprzedać nadwyżkę energii do sieci i ile.

        Ta metoda sprawdza, czy eksport energii jest możliwy, oblicza ilość, która może
        być sprzedana na podstawie aktualnych limitów i już sprzedanej energii,
        a następnie próbuje sprzedać nadwyżkę.

        Argumenty:
            power_surplus (float): Ilość nadwyżki energii dostępnej do sprzedaży w kW.

        Zwraca:
            dict: Słownik wskazujący na sukces próby sprzedaży i sprzedaną ilość.
        """
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
        """
        Ogranicza generację energii w celu zarządzania nadwyżką mocy. Gdy
        pozostałe metody zawiodły wywoływana jest ta metoda jako ostateczność.

        Ta metoda redukuje moc wyjściową urządzeń generujących w mikrosieci,
        zaczynając od urządzeń o najniższym priorytecie, aż do osiągnięcia
        wymaganej redukcji lub rozważenia wszystkich urządzeń.

        Argumenty:
            power_surplus (float): Ilość nadwyżki mocy do zredukowania w kW.

        Zwraca:
            dict: Słownik zawierający informacje o sukcesie operacji,
                  ilości zredukowanej mocy i ewentualnej pozostałej nadwyżce.
        """
        self.info_logger.info(
            f"Starting limit_energy_generation with power_surplus: {power_surplus}"
        )
        total_reduced = 0
        reasons = []

        active_generators = sorted(
            [
                device
                for device in self.microgrid.get_all_devices()
                if device.get_switch_status()
            ],
            key=lambda x: x.priority,
        )

        self.info_logger.info(
            f"Active generators: {[device.name for device in active_generators]}"
        )

        if not active_generators:
            reasons.append("No active generators found")

        for device in active_generators:
            if total_reduced >= power_surplus:
                break

            current_output = device.get_actual_output()
            min_output = device.get_min_output()
            reducible_power = current_output - min_output

            self.info_logger.info(
                f"Processing device: {device.name}, Current output: {current_output}, Min output: {min_output}, Reducible power: {reducible_power}"
            )

            if reducible_power <= 0:
                reasons.append(f"Device {device.name} cannot be reduced further")
                continue

            reduction = min(reducible_power, power_surplus - total_reduced)

            if reduction > 0:
                new_output = current_output - reduction
                action = f"set_output:{new_output}"
                self.info_logger.info(
                    f"Attempting to execute action: {action} for device {device.name}"
                )
                result = self.execute_action_func(device, action)
                self.info_logger.info(f"Result of execute_action_func: {result}")

                if result.get("pending", False):
                    self.info_logger.info(
                        f"Action pending for {device.name}: set output to {new_output} kW"
                    )
                    break
                elif result["success"]:
                    actual_reduction = current_output - device.get_actual_output()
                    total_reduced += actual_reduction
                    self.info_logger.info(
                        f"Reduced {device.name} (priority: {device.priority}) power by {actual_reduction} kW "
                        f"from {current_output} kW to {device.get_actual_output()} kW"
                    )
                else:
                    reasons.append(
                        f"Failed to reduce power for {device.name}. Reason: {result.get('reason', 'Unknown')}"
                    )

        remaining_surplus = power_surplus - total_reduced
        self.info_logger.info(f"Total power generation reduced: {total_reduced} kW")
        self.info_logger.info(f"Remaining surplus: {remaining_surplus} kW")

        if total_reduced == 0:
            self.info_logger.warning(
                f"Failed to reduce any power. Reasons: {', '.join(reasons)}"
            )

        return {
            "success": total_reduced > 0,
            "amount": total_reduced,
            "remaining_surplus": remaining_surplus,
            "reason": "; ".join(reasons) if reasons else "Unknown",
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

    def get_proposed_actions(self, power_surplus):
        proposed_actions = []
        active_generators = sorted(
            [
                device
                for device in self.microgrid.get_all_devices()
                if device.get_switch_status()
            ],
            key=lambda x: x.priority,
        )

        remaining_surplus = power_surplus
        action_id = 1

        for device in active_generators:
            if remaining_surplus <= 0:
                break

            current_output = device.get_actual_output()
            min_output = device.get_min_output()
            reducible_power = current_output - min_output

            if reducible_power <= 0:
                continue

            reduction = min(reducible_power, remaining_surplus)
            new_output = current_output - reduction

            proposed_actions.append(
                {
                    "id": action_id,
                    "device": device,
                    "action": f"set_output:{new_output}",
                    "current_output": current_output,
                    "proposed_output": new_output,
                    "reduction": reduction,
                }
            )

            remaining_surplus -= reduction
            action_id += 1

        return proposed_actions
