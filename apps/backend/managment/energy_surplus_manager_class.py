import uuid
from apps.backend.managment.surplus_action import SurplusAction
from apps.backend.managment.bess_decision_logic import should_prioritize_charging_or_selling
from apps.backend.managment.bess_decision_logic import (
    should_prioritize_charging_or_selling,
    DecisionConfig,
    DecisionMode
)


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
        energy_manager_ref=None  # ← DODAJ TO
        
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
        self.energy_manager_ref = energy_manager_ref  # ← DODAJ TO
        self.decision_config = self._load_decision_config()
    
    def _decide_bess_vs_grid(self, surplus: float):
        """
        Podejmuje decyzję BESS vs GRID dla nadwyżki energii.
        
        Args:
            surplus: Nadwyżka energii (kW)
            
        Returns:
            SurplusAction: Wybrana akcja
        """
        if not self.energy_manager_ref or not self.energy_manager_ref.microgrid.bess:
            self.info_logger.warning("BESS not available for decision")
            return SurplusAction.SELL_ENERGY
        
        bess = self.energy_manager_ref.microgrid.bess
        
        # Wywołaj funkcję decyzyjną
        result = should_prioritize_charging_or_selling(
            # BESS
            charge_level=bess.charge_level,
            min_charge_level=bess.min_charge_level,
            max_charge_level=bess.max_charge_level,
            
            # Sieć
            tariff_sell=self.osd.current_tariff_sell,
            tariff_buy=self.osd.current_tariff_buy,
            sold_power=self.osd.sold_power,
            sale_limit=self.osd.CONTRACTED_SALE_LIMIT,
            
            # Konfiguracja
            config=self.decision_config,
            
            # Logger
            info_logger=self.info_logger,
            error_logger=self.error_logger
        )
        
        # Loguj wynik
        self.info_logger.info(f"Decision: {result.reason}")
        self.info_logger.info(f"Confidence: {result.confidence*100:.1f}%")
        
        # Zwróć odpowiednią akcję
        if result.decision:  # CHARGE
            return SurplusAction.CHARGE_BATTERY
        else:  # SELL
            return SurplusAction.SELL_ENERGY

    def manage_surplus_energy(self, power_surplus):
        #  WALIDACJA DANYCH WEJŚCIOWYCH
        if not isinstance(power_surplus, (int, float)):
            self.error_logger.error(f"Invalid power_surplus type: {type(power_surplus)}. Expected float.")
            return {"amount_managed": 0, "remaining_surplus": power_surplus}
        
        if power_surplus <= 0:
            self.info_logger.info(f"Power surplus is {power_surplus} kW - no action needed")
            return {"amount_managed": 0, "remaining_surplus": 0}
        
        if power_surplus > 10000:  # Rozsądny limit
            self.error_logger.error(f"Power surplus too large: {power_surplus} kW. Maximum allowed: 10000 kW")
            return {"amount_managed": 0, "remaining_surplus": power_surplus}
        
        self.info_logger.info("")
        self.info_logger.info("MANAGING SURPLUS")
        
        total_managed = 0
        remaining_surplus = power_surplus
        iteration = 0
        MAX_ITERATIONS = 100
        attempted_actions = set()

        try:
            while remaining_surplus > self.EPSILON and iteration < MAX_ITERATIONS:
                iteration += 1
                self.info_logger.info(f"Iteration {iteration}, surplus remaining: {remaining_surplus:.1f} kW")

                #  POPRAWIONA LOGIKA ZGODNIE ZE SCENARIUSZEM
                # Krok 6: BESS vs GRID (decyzja)
                # Krok 7: Ograniczanie generacji (ostateczność)
                
                bess_available = self.check_bess_availability()
                export_possible = self.is_export_possible()
                
                # === KROK 6: BESS vs GRID (decyzja) ===
                if bess_available and export_possible:
                    # Obie opcje dostępne → DECYZJA (nie używamy BOTH)
                    self.info_logger.info(f"BESS can charge: {'YES' if bess_available else 'NO'}")
                    self.info_logger.info(f"GRID can export: {'YES' if export_possible else 'NO'}")
                    self.info_logger.info("Both options available → UTILITY FUNCTION")
                    action = self._decide_bess_vs_grid(remaining_surplus)
                elif bess_available and SurplusAction.CHARGE_BATTERY not in attempted_actions:
                    # Tylko BESS dostępne (i jeszcze nie próbowane)
                    self.info_logger.info("Only BESS available → CHARGE")
                    action = SurplusAction.CHARGE_BATTERY
                elif export_possible and SurplusAction.SELL_ENERGY not in attempted_actions:
                    # Tylko GRID dostępne (i jeszcze nie próbowane)
                    self.info_logger.info("Only GRID available → SELL")
                    action = SurplusAction.SELL_ENERGY
                else:
                    # === KROK 7: OSTATECZNOŚĆ - Ograniczanie generacji ===
                    if SurplusAction.LIMIT_GENERATION not in attempted_actions:
                        self.info_logger.info("Neither BESS nor GRID available (or already tried) → LIMIT GENERATION")
                        action = SurplusAction.LIMIT_GENERATION
                    else:
                        self.info_logger.warning("No more available actions to handle surplus.")
                        break
                
                attempted_actions.add(action)

                self.info_logger.info(f"Attempting: {action}")
                result = self.execute_action(action, remaining_surplus)

                if result["success"]:
                    total_managed += result["amount"]
                    remaining_surplus -= result["amount"]
                    self.info_logger.info(
                        f"Success: Managed {result['amount']:.1f} kW, remaining: {remaining_surplus:.1f} kW"
                    )
                    # Wyczyść attempted_actions po sukcesie - pozwól ponownie próbować w następnej iteracji
                    attempted_actions.clear()
                else:
                    self.info_logger.info(
                        f"Failed: {result.get('reason', 'Unknown')}"
                    )
                    # NIE czyść attempted_actions - akcja została już próbowana i failowała

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
        # Action już zalogowane w manage_surplus_energy()

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
        Decyduje czy ładować BESS.
        ZAKTUALIZOWANA: Używa BESSCapabilityChecker + planuje przyspieszoną iterację.
        
        Args:
            power_surplus: Nadwyżka mocy do załadowania (kW)
            
        Returns:
            dict: Wynik operacji ładowania
        """
        # Użyj capability checker jeśli dostępny
        if self.energy_manager_ref and self.energy_manager_ref.bess_checker:
            plan = self.energy_manager_ref.bess_checker.check_charge_capability(power_surplus)
            
            # Log planu
            self.energy_manager_ref.bess_checker.log_plan(plan, "charge")
            
            if not plan.is_feasible:
                return {
                    "success": False,
                    "amount": 0,
                    "percent": 0,
                    "reason": plan.reason
                }
            
            # Wykonaj ładowanie
            bess = self.microgrid.bess
            
            # POPRAWIONE: Sprawdź czy BESS już się ładuje aby obliczyć dodatkową moc
            previous_charge_power = abs(bess.setpoint_output) if bess.setpoint_output < 0 else 0
            
            # Ustaw nową całkowitą moc ładowania
            charged_amount, charged_percent = bess.charge(abs(plan.power_setpoint))
            
            # Oblicz dodatkową moc (przyrost) - to co faktycznie zarządzamy z surplus
            additional_power = abs(plan.power_setpoint) - previous_charge_power
            
            # Jeśli skończy się wcześniej - zaplanuj przyspieszoną iterację
            if plan.will_finish_before_next_iteration:
                self.energy_manager_ref.iteration_scheduler.schedule_early_iteration(
                    after_seconds=plan.time_to_completion_minutes * 60,
                    event_type="bess_charge_complete",
                    description=f"BESS will be full (charged {plan.energy_amount:.2f} kWh)"
                )
            
            # Dodaj tracking zmian
            if self.energy_manager_ref:
                device_change = {
                    "device": bess,
                    "action": f"charge:{additional_power}",  # Loguj przyrost, nie całość
                    "new_value": abs(plan.power_setpoint),  # Nowa całkowita moc
                    "device_type": "BESS"
                }
                self.energy_manager_ref.changed_devices.append(device_change)
                if previous_charge_power > 0:
                    self.info_logger.info(f"DEVICE CHANGED: {bess.name} (BESS) - increased charging from {previous_charge_power:.2f} to {abs(plan.power_setpoint):.2f} kW (+{additional_power:.2f} kW)")
                else:
                    self.info_logger.info(f"DEVICE CHANGED: {bess.name} (BESS) - charge:{additional_power}")
            
            return {
                "success": True,
                "amount": additional_power,  # Zwróć tylko dodatkową moc dla surplus management
                "percent": charged_percent
            }
        
        # Fallback - stary kod (jeśli brak checkera)
        try:
            if not self.check_bess_availability():
                return {
                    "success": False,
                    "amount": 0,
                    "percent": 0,
                    "reason": "BESS not available",
                }

            bess = self.microgrid.bess
            free_capacity = self.get_bess_free_capacity()

            if free_capacity <= self.EPSILON:
                return {
                    "success": False,
                    "amount": 0,
                    "percent": 0,
                    "reason": "BESS full",
                }

            amount_to_charge = min(power_surplus, free_capacity)
            charged_amount, charged_percent = bess.charge(amount_to_charge)

            if charged_amount > 0:
                self.info_logger.info(
                    f"BESS {bess.name} charged by {charged_amount:.2f} kWh ({charged_percent:.2f}%). "
                    f"New level: {bess.get_charge_level():.2f} kWh"
                )
                
                if self.energy_manager_ref:
                    device_change = {
                        "device": bess,
                        "action": f"charge:{charged_amount}",
                        "new_value": charged_amount,
                        "device_type": "BESS"
                    }
                    self.energy_manager_ref.changed_devices.append(device_change)
                    self.info_logger.info(f"DEVICE CHANGED: {bess.name} (BESS) - charge:{charged_amount}")
                
                return {
                    "success": True,
                    "amount": round(charged_amount, 6),
                    "percent": round(charged_percent, 2),
                }
            else:
                return {
                    "success": False,
                    "amount": 0,
                    "percent": 0,
                    "reason": "Failed to charge BESS",
                }
        except Exception as e:
            self.error_logger.error(f"Error in decide_to_charge_bess: {str(e)}")
            return {"success": False, "amount": 0, "percent": 0, "reason": str(e)}

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

    def sell_energy(self, power_surplus):
        try:
            self.osd.sell_power(power_surplus)
            # Śledzenie zmian OSD
            if self.energy_manager_ref:
                device_change = {
                    "device": self.osd,
                    "action": f"sell:{power_surplus}",
                    "new_value": power_surplus,
                    "device_type": "OSD"
                }
                self.energy_manager_ref.changed_devices.append(device_change)
            
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
                f"Processing device: {device.name}, Current output: {current_output:.6f}, "
                f"Min output: {min_output:.6f}, Reducible power: {reducible_power:.6f}"
            )

            if reducible_power <= self.EPSILON:
                reasons.append(f"Device {device.name} cannot be reduced further")
                continue

            #  ETAP 2: Zapisz stan PRZED ograniczeniem
            if self.energy_manager_ref:
                self.energy_manager_ref.save_device_state(device, "before_generation_limit")

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
                #  Ustaw setpoint dla SCADA
                if action == "deactivate":
                    device.setpoint_output = 0
                    new_output = 0
                else:
                    device.setpoint_output = new_output
                
                actual_reduction = current_output - new_output
                
                #  ETAP 2: Dodaj do listy ograniczeń
                if self.energy_manager_ref:
                    self.energy_manager_ref.add_artificial_limitation(
                        device=device,
                        limitation_type="generation_limit",
                        original_output=current_output,
                        new_output=new_output,
                        reduction=actual_reduction
                    )
                
                total_reduced += actual_reduction
                self.info_logger.info(
                    f"Reduced {device.name} (priority: {device.priority}) power by {actual_reduction:.6f} kW "
                    f"from {current_output:.6f} kW to {new_output:.6f} kW. "
                    f"Setpoint: {device.setpoint_output:.6f} kW"
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
        """Sprawdza czy Grid może eksportować (kontrakt + limit)"""
        try:
            # Sprawdź czy kontrakt pozwala na eksport
            if not self.osd.get_contracted_export_possibility():
                return False
            
            # Sprawdź czy Grid już nie eksportuje
            if self.energy_manager_ref:
                is_already_exporting, _ = self.energy_manager_ref.check_device_already_operating(
                    "GRID", "exporting"
                )
                if is_already_exporting:
                    return False
            
            # Sprawdź czy limit sprzedaży został osiągnięty
            if self.osd.get_sold_power() >= self.osd.get_sale_limit():
                return False
            
            return True
        except Exception as e:
            self.error_logger.error(f"Error checking export possibility: {str(e)}")
            return False

    def check_bess_availability(self):
        """
        Sprawdza czy BESS może ładować (rozpocząć lub zwiększyć ładowanie).
        
        POPRAWIONE: Zwraca True również gdy BESS już się ładuje ale można zwiększyć moc ładowania.
        """
        try:
            if not self.microgrid.bess.get_switch_status():
                return False
            
            # Sprawdź czy BESS ma wolne miejsce (to jest główny warunek)
            free_capacity = self.microgrid.bess.max_charge_level - self.microgrid.bess.charge_level
            if free_capacity <= 0:
                self.info_logger.debug("BESS unavailable: fully charged")
                return False
            
            # NOWE: Sprawdź czy można zwiększyć moc ładowania (jeśli już się ładuje)
            if self.energy_manager_ref:
                is_already_charging, current_charge_power = self.energy_manager_ref.check_device_already_operating(
                    "BESS", "charging"
                )
                if is_already_charging:
                    # BESS już się ładuje - sprawdź czy można zwiększyć moc
                    current_charge = abs(current_charge_power) if current_charge_power else 0
                    max_charge = self.microgrid.bess.max_charge_power
                    
                    if current_charge >= max_charge:
                        self.info_logger.debug(f"BESS unavailable: already charging at max power ({current_charge:.2f}/{max_charge:.2f} kW)")
                        return False
                    else:
                        self.info_logger.debug(f"BESS available: can increase charging from {current_charge:.2f} to {max_charge:.2f} kW")
                        return True  # Można zwiększyć ładowanie!
            
            # BESS nie ładuje się i ma wolne miejsce
            return True
            
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
        if not bess or not bess.get_switch_status():
            return None

        free_capacity = bess.get_capacity() - max(
            bess.get_charge_level(), bess.min_charge_level
        )
        amount_to_charge = min(power_surplus, free_capacity)

        if amount_to_charge <= self.EPSILON:
            return None

        return {
            "id": str(uuid.uuid4()),
            "device_id": bess.id,
            "device_name": bess.name,
            "device_type": "BESS",
            "action": f"charge:{amount_to_charge:.2f}",
            "current_output": bess.get_charge_level(),
            "proposed_output": min(
                bess.get_charge_level() + amount_to_charge, bess.get_capacity()
            ),
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
    
    def _load_decision_config(self) -> DecisionConfig:
        try:
            # Pobierz tryb z OSD (przychodzi z API jako 'decision_mode')
            mode_str = getattr(self.osd, 'decision_mode', 'AUTO').upper()
            
            # Mapowanie z API na DecisionMode
            mode_mapping = {
                "AUTO": DecisionMode.AUTO,
                "BESS_PRIORITY": DecisionMode.BESS_PRIORITY,
                "GRID_PRIORITY": DecisionMode.GRID_PRIORITY
            }
            
            if mode_str in mode_mapping:
                mode = mode_mapping[mode_str]
            else:
                self.error_logger.warning(f"Unknown decision_mode '{mode_str}', using AUTO")
                mode = DecisionMode.AUTO
            
            config = DecisionConfig(mode=mode)
            
            #self.info_logger.info(f"Decision config loaded: mode={config.mode.value}")
            
            return config
            
        except Exception as e:
            self.error_logger.error(f"Error loading decision config: {e}")
            return DecisionConfig()
        
    def handle_both_action(self, remaining_surplus):
        """
        Obsługuje akcję BOTH - ładowanie BESS i/lub sprzedaż.
        
        POPRAWIONY FLOW:
        1. Sprawdź fizyczne możliwości (BESSCapabilityChecker)
        2. Jeśli obie opcje dostępne → Decyzja (utility function)
        3. Wykonaj wybraną akcję
        """
        bess = self.microgrid.bess

        #  DODAJ TE LOGI DIAGNOSTYCZNE
        self.info_logger.info("=" * 70)
        self.info_logger.info("HANDLE_BOTH_ACTION - DEBUG")
        self.info_logger.info(f"  Remaining surplus: {remaining_surplus:.2f} kW")
        self.info_logger.info(f"  energy_manager_ref: {self.energy_manager_ref}")
        self.info_logger.info(f"  bess_checker: {self.energy_manager_ref.bess_checker if self.energy_manager_ref else None}")
        self.info_logger.info("=" * 70)
            
        # === KROK 1: SPRAWDŹ FIZYCZNE MOŻLIWOŚCI ===
    
        # Czy BESS może ładować?
        # 1A. Czy BESS może ładować?
        can_charge = False
        charge_plan = None
        
        if self.energy_manager_ref and self.energy_manager_ref.bess_checker:
            bess = self.energy_manager_ref.microgrid.bess
            
            #  ETAP 1: Sprawdź czy BESS już nie ładuje się!
            is_already_charging, charge_amount = self.energy_manager_ref.check_device_already_operating(
                "BESS", "charging"
            )
            
            if is_already_charging:
                self.info_logger.warning(
                    f"  BESS is ALREADY CHARGING {charge_amount:.2f} kW - cannot charge more"
                )
                can_charge = False
            else:
                # Sprawdź fizyczne możliwości ładowania
                charge_plan = self.energy_manager_ref.bess_checker.check_charge_capability(remaining_surplus)
                can_charge = charge_plan.is_feasible
                
                if can_charge:
                    self.info_logger.info(
                        f"✓ BESS can CHARGE: {charge_plan.energy_amount:.2f} kWh will be charged "
                        f"at {abs(charge_plan.power_setpoint):.2f} kW"
                    )
                    
                    # Opcjonalnie: log duration jeśli dostępny
                    if charge_plan.time_to_completion_minutes is not None:
                        self.info_logger.info(
                            f"  → Duration: {charge_plan.time_to_completion_minutes:.2f} min"
                        )
        
        # 1B. Czy Grid może eksportować?
        can_sell = self.osd.can_sell_energy()
        
        if can_sell:
            #  ETAP 1: Sprawdź czy Grid już nie eksportuje!
            is_already_exporting, export_amount = self.energy_manager_ref.check_device_already_operating(
                "GRID", "exporting"
            )
            
            if is_already_exporting:
                self.info_logger.warning(
                    f"  GRID is ALREADY EXPORTING {export_amount:.2f} kW - cannot export more"
                )
                can_sell = False
            else:
                remaining_capacity = self.osd.get_remaining_sale_capacity()
                self.info_logger.info(
                    f"✓ GRID can SELL: {remaining_capacity:.2f} kWh remaining capacity"
                )
        
        # === KROK 2: PODEJMIJ DECYZJĘ (tylko jeśli obie opcje dostępne) ===
        
        # Przypadek A: Tylko CHARGE możliwe
        if can_charge and not can_sell:
            self.info_logger.info(" Only CHARGE available → charging")
            return self._execute_charge(charge_plan, remaining_surplus)
        
        # Przypadek B: Tylko SELL możliwe
        if can_sell and not can_charge:
            self.info_logger.info("💰 Only SELL available → selling")
            return self._execute_sell(remaining_surplus)
        
        # Przypadek C: Obie opcje dostępne → DECYZJA
        if can_charge and can_sell:
            self.info_logger.info("  Both CHARGE and SELL available → making decision")
            
            # WYWOŁAJ FUNKCJĘ DECYZYJNĄ
            result = should_prioritize_charging_or_selling(
                # BESS
                charge_level=bess.charge_level,
                min_charge_level=bess.min_charge_level,
                max_charge_level=bess.max_charge_level,
                
                # Sieć
                tariff_sell=self.osd.current_tariff_sell,
                tariff_buy=self.osd.current_tariff_buy,
                sold_power=self.osd.sold_power,
                sale_limit=self.osd.CONTRACTED_SALE_LIMIT,
                
                # Konfiguracja
                config=self.decision_config,
                
                # Logger
                info_logger=self.info_logger,
                error_logger=self.error_logger
            )
            
            # Wynik już zalogowany w should_prioritize_charging_or_selling()
            
            # Wykonaj decyzję
            if result.decision:  # CHARGE
                return self._execute_charge(charge_plan, remaining_surplus)
            else:  # SELL
                return self._execute_sell(remaining_surplus)
        
        # Przypadek D: Żadna opcja niedostępna
        self.info_logger.warning("  Neither CHARGE nor SELL available")
        return {"success": False, "amount": 0, "reason": "No action possible"}


    def _execute_charge(self, charge_plan, remaining_surplus):
        """
        Wykonuje ładowanie BESS zgodnie z planem.
        
        Args:
            charge_plan: BESSOperationPlan z BESSCapabilityChecker
            remaining_surplus: Pozostała nadwyżka do zarządzenia (kW)
            
        Returns:
            dict: Wynik operacji ładowania
        """
        bess = self.microgrid.bess
        
        self.info_logger.info(f"Executing CHARGE: {abs(charge_plan.power_setpoint):.2f} kW")
        
        # Wykonaj ładowanie
        charged_amount, charged_percent = bess.charge(abs(charge_plan.power_setpoint))
        
        self.info_logger.info(
            f"BESS charged: {charged_amount:.2f} kWh ({charged_percent:.2f}%). "
            f"New level: {bess.charge_level:.2f} kWh"
        )
        
        # Zaplanuj przyspieszoną iterację (jeśli potrzeba)
        if charge_plan.will_finish_before_next_iteration and self.energy_manager_ref:
            self.energy_manager_ref.iteration_scheduler.schedule_early_iteration(
                after_seconds=charge_plan.time_to_completion_minutes * 60,
                event_type="bess_charge_complete",
                description=f"BESS will be full (charged {charge_plan.energy_amount:.2f} kWh)"
            )
            self.info_logger.info(
                f"⏰ Early iteration scheduled in {charge_plan.time_to_completion_minutes:.2f} min "
                f"({charge_plan.time_to_completion_minutes * 60:.0f}s)"
            )
        
        # Tracking zmian
        if self.energy_manager_ref:
            device_change = {
                "device": bess,
                "action": f"charge:{charged_amount}",
                "new_value": charged_amount,
                "device_type": "BESS"
            }
            self.energy_manager_ref.changed_devices.append(device_change)
            self.info_logger.info(f"DEVICE CHANGED: {bess.name} (BESS) - charge:{charged_amount:.2f}")
        
        # Jeśli nie udało się załadować całości → sprzedaj resztę
        # === EARLY ITERATION HANDLING ===

        if charge_plan.will_finish_before_next_iteration and self.energy_manager_ref:
            # BESS skończy wcześniej → zaplanuj early iteration
            self.energy_manager_ref.iteration_scheduler.schedule_early_iteration(
                after_seconds=charge_plan.time_to_completion_minutes * 60,
                event_type="bess_charge_complete",
                description=f"BESS will be full (charged {charge_plan.energy_amount:.2f} kWh)"
            )
            
            self.info_logger.info(
                f"⏰ Early iteration scheduled in {charge_plan.time_to_completion_minutes:.2f} min. "
                f"BESS setpoint will be set to 0 kW at that time. "
                f"Remaining surplus will be handled then."
            )
            
            #  NIE sprzedawaj reszty teraz - poczekaj na early iteration

        else:
            # BESS NIE skończy wcześniej → próbuj sprzedać resztę teraz
            if charged_amount < remaining_surplus - self.EPSILON:
                remaining = remaining_surplus - charged_amount
                self.info_logger.info(
                    f"Charged {charged_amount:.2f} kW, {remaining:.2f} kW remains. "
                    f"BESS won't finish early - attempting to sell remaining now."
                )
                
                # Sprawdź czy sell możliwe
                if self.is_export_possible():
                    remaining_limit = self.osd.CONTRACTED_SALE_LIMIT - self.osd.sold_power
                    if remaining_limit > self.EPSILON:
                        sell_result = self._execute_sell(remaining)
                        return {
                            "success": True,
                            "amount": charged_amount + sell_result.get("amount", 0),
                            "percent": charged_percent
                        }
                    else:
                        self.info_logger.warning("Cannot sell remaining - limit reached")
                else:
                    self.info_logger.warning("Cannot sell remaining - export not permitted")
        
        return {
            "success": True,
            "amount": charged_amount,
            "percent": charged_percent
        }


    def _execute_sell(self, amount):
        """
        Wykonuje sprzedaż energii.
        
        Args:
            amount: Ilość energii do sprzedaży (kW)
            
        Returns:
            dict: Wynik operacji sprzedaży
        """
        self.info_logger.info(f"Executing SELL: {amount:.2f} kW")
        
        sell_result = self.decide_to_sell_energy(amount)
        
        if sell_result["success"]:
            self.info_logger.info(f"Sold {sell_result['amount']:.2f} kW successfully")
        else:
            self.info_logger.warning(f"Failed to sell energy: {sell_result.get('reason', 'unknown')}")
        
        return sell_result
