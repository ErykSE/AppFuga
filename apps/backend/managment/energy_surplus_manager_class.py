import uuid
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

    def __init__(
        self,
        microgrid,
        osd,
        info_logger,
        error_logger,
        execute_action_func,
        add_to_tabu_func,
        is_in_tabu_func,
        clean_tabu_func,
    ):
        self.microgrid = microgrid
        self.osd = osd
        self.info_logger = info_logger
        self.error_logger = error_logger
        self.execute_action_func = execute_action_func
        self.previous_decision = True  # Domyślnie priorytet ładowania
        self.EPSILON = 1e-6  # Stała do porównywania liczb zmiennoprzecinkowych
        self.add_to_tabu = add_to_tabu_func
        self.is_in_tabu = is_in_tabu_func
        self.clean_tabu_list = (
            clean_tabu_func  # Zmienione z self.clean_tabu na self.clean_tabu_list
        )

    def manage_surplus_energy(self, power_surplus):
        total_managed = 0
        remaining_surplus = power_surplus
        iteration = 0
        MAX_ITERATIONS = 100
        attempted_actions = set()

        try:
            while remaining_surplus > self.EPSILON and iteration < MAX_ITERATIONS:
                iteration += 1
                self.info_logger.info(
                    f"Iteration {iteration}, surplus remaining: {remaining_surplus:.6f} kW"
                )

                bess_available = self.check_bess_availability()
                export_possible = self.is_export_possible()

                # Określamy dostępne akcje
                available_actions = []
                if (
                    bess_available
                    and export_possible
                    and SurplusAction.BOTH not in attempted_actions
                ):
                    available_actions.append(SurplusAction.BOTH)
                if (
                    bess_available
                    and SurplusAction.CHARGE_BATTERY not in attempted_actions
                ):
                    available_actions.append(SurplusAction.CHARGE_BATTERY)
                if (
                    export_possible
                    and SurplusAction.SELL_ENERGY not in attempted_actions
                ):
                    available_actions.append(SurplusAction.SELL_ENERGY)
                if SurplusAction.LIMIT_GENERATION not in attempted_actions:
                    available_actions.append(SurplusAction.LIMIT_GENERATION)

                if not available_actions:
                    self.info_logger.warning(
                        "No more available actions to handle surplus."
                    )
                    break

                action = available_actions[0]  # Wybieramy pierwszą dostępną akcję
                attempted_actions.add(action)

                self.info_logger.info(f"Attempting to perform the action: {action}")
                result = self.execute_action(action, remaining_surplus)
                self.info_logger.info(f"Action result: {result}")

                if result["success"]:
                    total_managed += result["amount"]
                    remaining_surplus -= result["amount"]
                    self.info_logger.info(
                        f"Action {action} managed {result['amount']:.6f} kW. Surplus remaining: {remaining_surplus:.6f} kW"
                    )
                else:
                    self.info_logger.info(
                        f"Action {action} has failed. Reason: {result.get('reason', 'Unknown')}"
                    )

            if iteration == MAX_ITERATIONS:
                self.error_logger.error(
                    f"The maximum number of iterations ({MAX_ITERATIONS}) has been reached without solving the surplus."
                )

        except Exception as e:
            self.error_logger.error(f"Error in manage_surplus_energy: {str(e)}")
            self.error_logger.exception("Full traceback:")

        return {
            "amount_managed": round(total_managed, 6),
            "remaining_surplus": round(remaining_surplus, 6),
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
        self.info_logger.info(
            f"XXXXXXXXXXXXXXXXXXXXXXXXXExecuting actionxdxdxdd: {action}"
        )
        self.info_logger.info(f"Remaining surplus: {remaining_surplus:.6f}")

        if action == SurplusAction.BOTH:
            return self.handle_both_action(remaining_surplus)
        elif action == SurplusAction.CHARGE_BATTERY:
            return self.decide_to_charge_bess(remaining_surplus)
        elif action == SurplusAction.SELL_ENERGY:
            return self.decide_to_sell_energy(remaining_surplus)
        elif action == SurplusAction.LIMIT_GENERATION:
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
        MIN_SELLING_PRICE = 0.01
        MAX_SELLING_PRICE = 2.25
        BATTERY_THRESHOLD = 20
        PRICE_THRESHOLD = 0.7
        HYSTERESIS = 0.05

        if battery_free_percentage <= BATTERY_THRESHOLD:
            return True

        if battery_free_percentage == 0:
            return False

        # price_factor = (current_selling_price - MIN_SELLING_PRICE) / (
        # MAX_SELLING_PRICE - MIN_SELLING_PRICE
        # )
        # price_factor = max(0, min(price_factor, 1))

        # battery_factor = 1 - (battery_free_percentage / 100)
        price_factor = 0.2
        battery_factor = 0.1

        self.info_logger.info(
            f"Batteryxxx ({battery_factor}) price ({price_factor} kW)"
        )

        # battery_factor = 0.77

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
                f"xxxx: price factor ({price_factor:.2f}) > battery factor ({battery_factor:.2f})"
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
                return {"success": False, "amount": 0, "reason": "BESS not available"}

            bess = self.microgrid.bess
            free_capacity = self.get_bess_free_capacity()

            if free_capacity <= self.EPSILON:
                return {"success": False, "amount": 0, "reason": "BESS full"}

            amount_to_charge = min(power_surplus, free_capacity)
            percent_to_charge = (amount_to_charge / bess.get_capacity()) * 100
            charged_percent, actual_charge = bess.try_charge(percent_to_charge)

            self.info_logger.info(
                f"BESS charged by {actual_charge:.2f} kW. New level: {bess.get_charge_level():.2f} kWh"
            )
            return {"success": True, "amount": round(actual_charge, 6)}
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

            if remaining_sale_capacity <= self.EPSILON:
                self.info_logger.info(
                    "The sales limit has been reached. No more energy can be sold."
                )
                return {"success": False, "amount": 0, "reason": "Sales limit reached"}

            amount_to_sell = min(power_surplus, remaining_sale_capacity)

            if amount_to_sell > self.EPSILON:
                sold_amount = self.sell_energy(amount_to_sell)
                if sold_amount > 0:
                    self.info_logger.info(
                        f"Successfully sold {sold_amount:.6f} kW of energy."
                    )
                    return {"success": True, "amount": round(sold_amount, 6)}
                else:
                    return {
                        "success": False,
                        "amount": 0,
                        "reason": "Failed to sell energy",
                    }
            else:
                return {"success": False, "amount": 0, "reason": "No energy to sell"}
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
            if (
                not result["success"]
                or result["amount"] < remaining_surplus - self.EPSILON
            ):
                sell_result = self.decide_to_sell_energy(
                    remaining_surplus - result["amount"]
                )
                result["amount"] += sell_result["amount"]
                result["success"] = result["success"] or sell_result["success"]
        else:
            result = self.decide_to_sell_energy(remaining_surplus)
            if (
                not result["success"]
                or result["amount"] < remaining_surplus - self.EPSILON
            ):
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
        Ogranicza generację energii w celu zarządzania nadwyżką mocy.
        """
        self.info_logger.info(
            f"Starting limit_energy_generation with power_surplus: {power_surplus:.6f}"
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
            if total_reduced >= power_surplus - self.EPSILON:
                break

            current_output = device.get_actual_output()
            min_output = device.get_min_output()
            reducible_power = current_output - min_output

            self.info_logger.info(
                f"Processing device: {device.name}, Current output: {current_output:.6f}, Min output: {min_output:.6f}, Reducible power: {reducible_power:.6f}"
            )

            if reducible_power <= self.EPSILON:
                reasons.append(f"Device {device.name} cannot be reduced further")
                continue

            if device.is_adjustable:
                reduction = min(reducible_power, power_surplus - total_reduced)
                new_output = round(current_output - reduction, 6)
                action = f"set_output:{new_output}"
            else:
                # Dla nieregulowanych urządzeń, możemy tylko wyłączyć
                reduction = current_output
                action = "deactivate"

            self.info_logger.info(
                f"Attempting to execute action: {action} for device {device.name}"
            )
            result = self.execute_action_func(device, action)
            self.info_logger.info(f"Result of execute_action_func: {result}")

            if result.get("pending", False):
                self.info_logger.info(f"Action pending for {device.name}: {action}")
                break
            elif result["success"]:
                actual_reduction = current_output - device.get_actual_output()
                total_reduced += actual_reduction
                self.info_logger.info(
                    f"Reduced {device.name} (priority: {device.priority}) power by {actual_reduction:.6f} kW "
                    f"from {current_output:.6f} kW to {device.get_actual_output():.6f} kW"
                )
            else:
                reasons.append(
                    f"Failed to reduce power for {device.name}. Reason: {result.get('reason', 'Unknown')}"
                )

        remaining_surplus = power_surplus - total_reduced
        self.info_logger.info(f"Total power generation reduced: {total_reduced:.6f} kW")
        self.info_logger.info(f"Remaining surplus: {remaining_surplus:.6f} kW")

        if total_reduced == 0:
            self.info_logger.warning(
                f"Failed to reduce any power. Reasons: {', '.join(reasons)}"
            )

        return {
            "success": total_reduced > self.EPSILON,
            "amount": round(total_reduced, 6),
            "remaining_surplus": round(remaining_surplus, 6),
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
        self.clean_tabu_list()
        self.info_logger.info(f"Checking tabu list before proposing actions")
        self.info_logger.info(f"BESS id: {self.microgrid.bess.id}")
        self.info_logger.info(
            f"BESS in tabu: {self.is_in_tabu(self.microgrid.bess.id)}"
        )

        bess = self.microgrid.bess
        osd = self.osd

        bess_available = (
            bess.get_switch_status()
            and not self.is_in_tabu(bess.id)
            and bess.is_uncharged()
        )
        export_possible = (
            osd.get_contracted_export_possibility()
            and not self.is_in_tabu("OSD")
            and osd.can_sell_energy()
        )

        self.info_logger.info(
            f"BESS available: {bess_available}, Export possible: {export_possible}"
        )
        self.info_logger.info(
            f"BESS charge level: {bess.get_charge_level()} / {bess.get_capacity()} kWh"
        )
        self.info_logger.info(
            f"OSD remaining sale capacity: {osd.get_remaining_sale_capacity()} kWh"
        )

        actions = []
        remaining_surplus = power_surplus

        if bess_available and export_possible:
            self.info_logger.info(
                "#################Selected action: SurplusAction.BOTH"
            )
            actions = self.prepare_both_actions(remaining_surplus)
        elif bess_available:
            self.info_logger.info(
                "##################Selected action: SurplusAction.CHARGE_BATTERY"
            )
            bess_action = self.prepare_bess_action(remaining_surplus)
            if bess_action:
                actions.append(bess_action)
        elif export_possible:
            self.info_logger.info(
                "##############Selected action: SurplusAction.SELL_ENERGY"
            )
            sell_action = self.prepare_sell_action(remaining_surplus)
            if sell_action:
                actions.append(sell_action)
        else:
            self.info_logger.info(
                "##############Selected action: SurplusAction.LIMIT_GENERATION"
            )
            actions = self.prepare_limit_actions(remaining_surplus)
            return actions  # Zwracamy tylko akcje limitowania, jeśli to jedyna opcja

        # Oblicz pozostałą nadwyżkę po zaproponowanych akcjach
        for action in actions:
            remaining_surplus -= action["reduction"]

        # Jeśli nadal jest nadwyżka, dodaj akcję LIMIT_GENERATION
        if remaining_surplus > self.EPSILON:
            self.info_logger.info(
                f"Remaining surplus after primary actions: {remaining_surplus:.2f} kW"
            )
            self.info_logger.info(
                "Adding LIMIT_GENERATION action for remaining surplus"
            )
            limit_actions = self.prepare_limit_actions(remaining_surplus)
            actions.extend(limit_actions)

        return actions

    def prepare_both_actions(self, power_surplus):
        battery_free_percentage = self.get_bess_free_percentage()
        current_selling_price = self.osd.get_current_sell_price()
        should_charge = self.should_prioritize_charging_or_selling(
            power_surplus, battery_free_percentage, current_selling_price
        )

        actions = []
        remaining_surplus = power_surplus

        if should_charge:
            bess_action = self.prepare_bess_action(remaining_surplus)
            if bess_action:
                actions.append(bess_action)
                remaining_surplus -= bess_action["reduction"]

            if remaining_surplus > self.EPSILON:
                sell_action = self.prepare_sell_action(remaining_surplus)
                if sell_action:
                    actions.append(sell_action)
        else:
            sell_action = self.prepare_sell_action(remaining_surplus)
            if sell_action:
                actions.append(sell_action)
                remaining_surplus -= sell_action["reduction"]

            if remaining_surplus > self.EPSILON:
                bess_action = self.prepare_bess_action(remaining_surplus)
                if bess_action:
                    actions.append(bess_action)

        return actions

    def prepare_action(self, action_type, power_surplus):
        if action_type == SurplusAction.BOTH:
            bess_action = self.prepare_bess_action(power_surplus)
            sell_action = self.prepare_sell_action(power_surplus)
            return [
                action for action in [bess_action, sell_action] if action is not None
            ]
        elif action_type == SurplusAction.CHARGE_BATTERY:
            bess_action = self.prepare_bess_action(power_surplus)
            return [bess_action] if bess_action is not None else []
        elif action_type == SurplusAction.SELL_ENERGY:
            sell_action = self.prepare_sell_action(power_surplus)
            return [sell_action] if sell_action is not None else []
        elif action_type == SurplusAction.LIMIT_GENERATION:
            return self.prepare_limit_actions(power_surplus)
        else:
            return []

    def prepare_bess_action(self, power_surplus):
        bess = self.microgrid.bess
        free_capacity = bess.get_capacity() - bess.get_charge_level()
        amount_to_charge = min(power_surplus, free_capacity)

        if amount_to_charge <= self.EPSILON:
            return None

        return {
            "id": str(uuid.uuid4()),
            "device_id": bess.id,
            "device_name": bess.name,
            "device_type": "BESS",
            "action": f"charge:{amount_to_charge}",
            "current_output": bess.get_charge_level(),
            "proposed_output": bess.get_charge_level() + amount_to_charge,
            "reduction": amount_to_charge,
        }

    def prepare_sell_action(self, power_surplus):
        remaining_sale_capacity = self.osd.get_remaining_sale_capacity()
        amount_to_sell = min(power_surplus, remaining_sale_capacity)

        if amount_to_sell <= self.EPSILON:
            return None

        return {
            "id": str(uuid.uuid4()),
            "device_id": "OSD",
            "device_name": "OSD",
            "device_type": "OSD",
            "action": f"sell:{amount_to_sell}",
            "current_output": self.osd.get_sold_power(),
            "proposed_output": self.osd.get_sold_power() + amount_to_sell,
            "reduction": amount_to_sell,
        }

    def prepare_limit_actions(self, power_surplus):
        actions = []
        active_generators = sorted(
            [
                device
                for device in self.microgrid.get_all_devices()
                if device.get_switch_status()
            ],
            key=lambda x: x.priority,
        )

        remaining_surplus = power_surplus
        for device in active_generators:
            current_output = device.get_actual_output()
            min_output = device.get_min_output()
            reducible_power = current_output - min_output

            if reducible_power > self.EPSILON:
                if device.is_adjustable:
                    reduction = min(reducible_power, remaining_surplus)
                    new_output = current_output - reduction
                    action = f"set_output:{new_output:.2f}"
                else:
                    # Dla nieregulowanych urządzeń, proponujemy tylko wyłączenie
                    reduction = current_output
                    action = "deactivate"

                actions.append(
                    {
                        "id": str(uuid.uuid4()),
                        "device_id": device.id,
                        "device_name": device.name,
                        "device_type": type(device).__name__,
                        "action": action,
                        "current_output": current_output,
                        "proposed_output": current_output - reduction,
                        "reduction": reduction,
                    }
                )
                remaining_surplus -= reduction

            if remaining_surplus <= self.EPSILON:
                break

        return actions

    def can_charge_bess(self, amount):
        if not self.check_bess_availability():
            return False
        free_capacity = self.get_bess_free_capacity()
        return free_capacity > self.EPSILON and amount > 0
