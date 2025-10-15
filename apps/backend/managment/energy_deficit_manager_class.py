import uuid
import logging
from collections import defaultdict

from apps.backend.managment.deficit_action import DeficitAction
from apps.backend.devices.adjustable_devices import AdjustableDevice
from apps.backend.devices.non_adjustable import NonAdjustableDevice
from apps.backend.managment.bess_decision_logic import (
    should_prioritize_discharging_or_buying,
    DecisionConfig,
    DecisionMode
)


class EnergyDeficitManager:
    """
    Klasa odpowiedzialna za zarządzanie deficytem energii w systemie mikrosieci.

    Ta klasa implementuje różne strategie obsługi niedoboru energii,
    w tym maksymalizację produkcji, rozładowywanie akumulatorów,
    zakup energii i ograniczanie zużycia przez odbiory. Priorytetyzuje działania
    w oparciu o aktualny stan systemu, poziomy naładowania akumulatorów
    i ceny energii.

    Atrybuty:
        microgrid (Microgrid): Zarządzany system mikrosieci.
        consumergrid (ConsumerGrid): Zarządzany system odbiorców energii.
        osd (OSD): Obiekt zawierający dane dotyczące informacji kontraktowych pomiędzy przedsiębiorstwem, a dostawcą.
        info_logger (Logger): Logger do wiadomości informacyjnych.
        error_logger (Logger): Logger do wiadomości o błędach.
        previous_discharge_decision (bool): Flaga przechowująca poprzednią decyzję o rozładowaniu dla histerezy.
    """

    def __init__(
        self,
        microgrid,
        consumergrid,
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
        self.consumergrid = consumergrid
        self.osd = osd
        self.info_logger = info_logger
        self.error_logger = error_logger
        self.execute_action_func = execute_action_func
        self.add_to_tabu = add_to_tabu_func
        self.is_in_tabu = is_in_tabu_func
        self.clean_tabu_list = clean_tabu_func
        self.previous_discharge_decision = False
        self.MAX_EXCESS_PERCENTAGE = 0.85  # Dodaj tę linię
        self.energy_manager_ref = energy_manager_ref  # ← DODAJ TO
        self.EPSILON = 1e-6
        self.decision_config = self._load_decision_config()

    def handle_deficit_automatic(self, power_deficit):
        """
        Zarządza deficytem energii poprzez wykonywanie odpowiednich działań.

        Ta metoda próbuje obsłużyć deficyt energii poprzez serię działań,
        w tym maksymalizację produkcji, rozładowywanie akumulatorów,
        zakup energii i ograniczanie zużycia. Kontynuuje, dopóki deficyt
        nie zostanie w pełni zarządzony lub nie zostaną wyczerpane wszystkie opcje.

        Argumenty:
            power_deficit (float): Ilość deficytu energii do zarządzania w kW.

        Zwraca:
            dict: Słownik zawierający ilość zarządzonego deficytu i ewentualny pozostały deficyt.
        """
        # ✅ WALIDACJA DANYCH WEJŚCIOWYCH
        if not isinstance(power_deficit, (int, float)):
            self.error_logger.error(f"Invalid power_deficit type: {type(power_deficit)}. Expected float.")
            return {"amount_managed": 0, "remaining_deficit": power_deficit}
        
        if power_deficit <= 0:
            self.info_logger.info(f"Power deficit is {power_deficit} kW - no action needed")
            return {"amount_managed": 0, "remaining_deficit": 0}
        
        if power_deficit > 10000:  # Rozsądny limit
            self.error_logger.error(f"Power deficit too large: {power_deficit} kW. Maximum allowed: 10000 kW")
            return {"amount_managed": 0, "remaining_deficit": power_deficit}
        
        self.info_logger.info(f"Start managing power deficit: {power_deficit} kW")

        managed = self.maximize_power_output(power_deficit)

        self.info_logger.info(
            f"Power was ordered by increasing production: {managed} kW"
        )
        remaining_deficit = power_deficit - managed

        if remaining_deficit > 0:
            self.info_logger.info(
                f"Remaining deficit after maximisation of equipment operation: {remaining_deficit} kW"
            )
            result = self.manage_remaining_deficit(remaining_deficit)
            managed += result["amount_managed"]
            remaining_deficit = result["remaining_deficit"]

        self.info_logger.info(
            f"Deficit management completed. A total of managed: {managed} kW. Remaining deficit: {remaining_deficit} kW"
        )
        return {
            "amount_managed": managed,
            "remaining_deficit": remaining_deficit,
        }

    def can_handle_more_power(self, power_deficit):
        """
        Oblicza, ile dodatkowej mocy system może obsłużyć.

        Ta metoda analizuje aktualny stan systemu, w tym pojemność BESS i możliwości sprzedaży,
        aby określić, ile dodatkowej mocy może być wygenerowane i obsłużone.

        Argumenty:
            power_deficit (float): Aktualny deficyt energii w kW.

        Zwraca:
            float: Ilość dodatkowej mocy, którą system może obsłużyć w kW.
        """
        bess_free_capacity = (
            self.microgrid.bess.get_capacity() - self.microgrid.bess.get_charge_level()
            if self.microgrid.bess
            else 0
        )
        # Oblicz dostępną pojemność sprzedaży
        sale_capacity = self.osd.get_remaining_sale_capacity()

        # Oblicz całkowitą dostępną pojemność do zagospodarowania nadwyżki
        total_available_capacity = bess_free_capacity + sale_capacity

        # Oblicz potencjalną nadwyżkę
        current_output = self.microgrid.total_power_generated()
        max_potential_output = sum(
            device.get_max_output() for device in self.microgrid.get_all_devices()
        )
        potential_surplus = max_potential_output - current_output - power_deficit

        # Oblicz, ile dodatkowej mocy możemy obsłużyć
        handleable_power = min(total_available_capacity, potential_surplus)

        self.info_logger.info(f"Current output: {current_output} kW")
        self.info_logger.info(f"Max potential output: {max_potential_output} kW")
        self.info_logger.info(f"Power deficit: {power_deficit} kW")
        self.info_logger.info(f"Potential surplus: {potential_surplus} kW")
        self.info_logger.info(f"BESS free capacity: {bess_free_capacity} kWh")
        self.info_logger.info(f"Available sale capacity: {sale_capacity} kWh")
        self.info_logger.info(
            f"Total available capacity: {total_available_capacity} kWh"
        )
        self.info_logger.info(f"Handleable additional power: {handleable_power} kW")

        return handleable_power

    def maximize_power_output(self, power_deficit):
        """
        Maksymalizuje produkcję energii w celu pokrycia deficytu.

        Ta metoda zwiększa moc wyjściową aktywnych urządzeń generujących
        i aktywuje nieaktywne urządzenia, jeśli to konieczne, aby pokryć
        deficyt energii. Urządzenia są priorytetyzowane według ich wartości priorytetu.

        Argumenty:
            power_deficit (float): Ilość deficytu energii do pokrycia w kW.

        Zwraca:
            float: Ilość zwiększonej mocy wyjściowej w kW.
        """
        # ✅ WALIDACJA DANYCH WEJŚCIOWYCH
        if not isinstance(power_deficit, (int, float)) or power_deficit <= 0:
            self.error_logger.error(f"Invalid power_deficit: {power_deficit}")
            return 0.0
        
        if not self.microgrid or not hasattr(self.microgrid, 'get_all_devices'):
            self.error_logger.error("Microgrid not available or invalid")
            return 0.0
        
        handleable_power = self.can_handle_more_power(power_deficit)

        current_output = self.microgrid.total_power_generated()
        max_potential_output = sum(
            device.get_max_output() for device in self.microgrid.get_all_devices()
        )
        target_output = min(current_output + power_deficit, max_potential_output)

        self.info_logger.info(f"Current output: {current_output} kW")
        self.info_logger.info(f"Max potential output: {max_potential_output} kW")
        self.info_logger.info(f"Power deficit: {power_deficit} kW")
        self.info_logger.info(f"Handleable power: {handleable_power} kW")
        self.info_logger.info(f"Target output: {target_output} kW")

        increased_power = 0

        # Sortujemy wszystkie urządzenia według priorytetu (rosnąco)
        all_devices = sorted(self.microgrid.get_all_devices(), key=lambda x: x.priority)

        # Najpierw zwiększamy moc aktywnych urządzeń
        for device in all_devices:
            # Sprawdź czy już osiągnęliśmy cel
            if current_output + increased_power >= target_output:
                break

            if device.get_switch_status():  # Jeśli urządzenie jest aktywne
                initial_output = device.get_actual_output()
                max_output = device.get_max_output()

                if device.is_adjustable:
                    # Oblicz ile jeszcze potrzebujemy
                    remaining_needed = target_output - (current_output + increased_power)
                    # Nowa moc = początkowa + to co potrzebujemy (ale nie więcej niż max)
                    new_output = min(max_output, initial_output + remaining_needed)
                    if device.set_output(new_output):
                        actual_increase = new_output - initial_output
                        increased_power += actual_increase
                        # DODAJ TO:
                        if self.energy_manager_ref:
                            device_change = {
                                "device": device,
                                "action": f"set_output:{new_output}",
                                "new_value": actual_increase,
                                "device_type": self.energy_manager_ref.get_device_type(device)
                            }
                            self.energy_manager_ref.changed_devices.append(device_change)
                            self.info_logger.info(f"DEVICE CHANGED: {device.name} ({self.energy_manager_ref.get_device_type(device)}) - set_output:{new_output}")
                        
                        self.info_logger.info(
                            f"Increased power of adjustable device {device.name} "
                            f"(priority: {device.priority}) from {initial_output} kW to {new_output} kW"
                        )
                elif initial_output < max_output:
                    if device.set_output(max_output):
                        actual_increase = max_output - initial_output
                        increased_power += actual_increase
                        # DODAJ TO:
                        if self.energy_manager_ref:
                            device_change = {
                                "device": device,
                                "action": f"set_output:{max_output}",
                                "new_value": actual_increase,
                                "device_type": self.energy_manager_ref.get_device_type(device)
                            }
                            self.energy_manager_ref.changed_devices.append(device_change)
                            self.info_logger.info(f"DEVICE CHANGED: {device.name} ({self.energy_manager_ref.get_device_type(device)}) - set_output:{max_output}")
                        
                        self.info_logger.info(
                            f"Set non-adjustable device {device.name} "
                            f"(priority: {device.priority}) to maximum output: {max_output} kW"
                        )

        # Jeśli nadal potrzebujemy więcej mocy, aktywujemy nieaktywne urządzenia
        if current_output + increased_power < target_output:
            for device in all_devices:
                if current_output + increased_power >= target_output:
                    break

                if not device.get_switch_status():  # Jeśli urządzenie jest nieaktywne
                    if device.activate():
                        max_output = device.get_max_output()
                        if device.is_adjustable:
                            # Oblicz ile jeszcze potrzebujemy
                            remaining_needed = target_output - (current_output + increased_power)
                            # Nowa moc = to co potrzebujemy (ale nie więcej niż max)
                            new_output = min(max_output, remaining_needed)
                            if device.set_output(new_output):
                                actual_increase = new_output
                                increased_power += actual_increase
                                # DODAJ TO:
                                if self.energy_manager_ref:
                                    device_change = {
                                        "device": device,
                                        "action": f"activate_and_set:{new_output}",
                                        "new_value": actual_increase,
                                        "device_type": self.energy_manager_ref.get_device_type(device)
                                    }
                                    self.energy_manager_ref.changed_devices.append(device_change)
                                    self.info_logger.info(f"DEVICE CHANGED: {device.name} ({self.energy_manager_ref.get_device_type(device)}) - activate_and_set:{new_output}")
                                
                                self.info_logger.info(
                                    f"Activated adjustable device {device.name} "
                                    f"(priority: {device.priority}) and set power to {new_output} kW"
                                )
                        else:
                            if device.set_output(max_output):
                                actual_increase = max_output
                                increased_power += actual_increase
                                # DODAJ TO:
                                if self.energy_manager_ref:
                                    device_change = {
                                        "device": device,
                                        "action": f"activate_and_set:{max_output}",
                                        "new_value": actual_increase,
                                        "device_type": self.energy_manager_ref.get_device_type(device)
                                    }
                                    self.energy_manager_ref.changed_devices.append(device_change)
                                    self.info_logger.info(f"DEVICE CHANGED: {device.name} ({self.energy_manager_ref.get_device_type(device)}) - activate_and_set:{max_output}")
                                
                                self.info_logger.info(
                                    f"Activated non-adjustable device {device.name} "
                                    f"(priority: {device.priority}) and set to maximum power: {max_output} kW"
                                )

        self.info_logger.info(f"In total, power was increased by {increased_power} kW")
        self.info_logger.info(f"Final output: {current_output + increased_power} kW")
        return increased_power

    """
    POPRAWIONA GŁÓWNA PĘTLA DEFICYTU
    Spójna struktura z surplus_manager.py
    """

    def manage_remaining_deficit(self, remaining_deficit):
        """
        Zarządza pozostałym deficytem energii po maksymalizacji produkcji.
        
        ✅ POPRAWIONA STRUKTURA - zawsze przez _execute_* metody!
        
        Args:
            remaining_deficit: Pozostały deficyt energii do zarządzania w kW.
            
        Returns:
            dict: Słownik zawierający ilość zarządzonego deficytu i ewentualny pozostały deficyt.
        """
        total_managed = 0
        iteration = 0
        MAX_ITERATIONS = 100

        while remaining_deficit > self.EPSILON and iteration < MAX_ITERATIONS:
            iteration += 1
            self.info_logger.info(
                f"Iteration {iteration}, remaining deficit: {remaining_deficit} kW"
            )

            # Sprawdź możliwości
            bess_available = self.is_bess_available()
            can_buy_energy = self.can_buy_energy()

            # === NOWA LOGIKA - SPÓJNA Z SURPLUS ===
            
            if bess_available and can_buy_energy:
                # ✅ Obie opcje → handle_deficit_both_action()
                self.info_logger.info("Both DISCHARGE and BUY available → using smart decision")
                result = self.handle_deficit_both_action(remaining_deficit)
                
                if result["success"]:
                    total_managed += result["amount"]
                    remaining_deficit -= result["amount"]
                    self.info_logger.info(
                        f"Smart decision handled {result['amount']:.2f} kW. "
                        f"Remaining deficit: {remaining_deficit:.2f} kW"
                    )
                else:
                    self.info_logger.warning(
                        f"Failed to handle deficit: {result.get('reason', 'unknown')}"
                    )
                    # Jeśli nie udało się - spróbuj ograniczyć zużycie
                    break

            elif bess_available:
                # ✅ Tylko DISCHARGE → _execute_discharge()
                self.info_logger.info("Only BESS available → discharging")
                
                # Sprawdź capability
                discharge_plan = None
                if self.energy_manager_ref and self.energy_manager_ref.bess_checker:
                    discharge_plan = self.energy_manager_ref.bess_checker.check_discharge_capability(remaining_deficit)
                    if not discharge_plan.is_feasible:
                        self.info_logger.warning(f"BESS discharge not feasible: {discharge_plan.reason}")
                        break
                
                result = self._execute_discharge(discharge_plan, remaining_deficit)
                
                if result["success"]:
                    total_managed += result["amount"]
                    remaining_deficit -= result["amount"]
                    self.info_logger.info(
                        f"BESS discharge handled {result['amount']:.2f} kW. "
                        f"Remaining deficit: {remaining_deficit:.2f} kW"
                    )
                else:
                    self.info_logger.warning(f"BESS discharge failed: {result.get('reason', 'unknown')}")
                    break

            elif can_buy_energy:
                # ✅ Tylko BUY → _execute_buy()
                self.info_logger.info("Only BUY available → buying from grid")
                result = self._execute_buy(remaining_deficit)
                
                if result["success"]:
                    total_managed += result["amount"]
                    remaining_deficit -= result["amount"]
                    self.info_logger.info(
                        f"Energy purchase handled {result['amount']:.2f} kW. "
                        f"Remaining deficit: {remaining_deficit:.2f} kW"
                    )
                else:
                    self.info_logger.warning(f"Energy purchase failed: {result.get('reason', 'unknown')}")
                    break

            else:
                # ❌ Żadna opcja niedostępna → ograniczenie zużycia (ostateczność)
                self.info_logger.warning("Neither DISCHARGE nor BUY available → limiting consumption")
                result = self.execute_action(DeficitAction.LIMIT_CONSUMPTION, remaining_deficit)
                
                if result["success"]:
                    total_managed += result["amount"]
                    remaining_deficit -= result["amount"]
                    self.info_logger.info(
                        f"Consumption limitation handled {result['amount']:.2f} kW. "
                        f"Remaining deficit: {remaining_deficit:.2f} kW"
                    )
                    if "devices_affected" in result:
                        for device in result["devices_affected"]:
                            self.info_logger.info(f"  - {device}")
                else:
                    self.info_logger.warning(
                        f"Failed to limit consumption. Reason: {result.get('error', 'Unknown')}"
                    )
                    if remaining_deficit == result.get("remaining_deficit", remaining_deficit):
                        self.error_logger.error("No further reduction possible. Exiting loop.")
                        break

            self.info_logger.info(
                f"After iteration {iteration}: "
                f"Total managed {total_managed:.2f} kW, "
                f"remaining deficit {remaining_deficit:.2f} kW"
            )

        if iteration == MAX_ITERATIONS:
            self.error_logger.error(
                f"Maximum iterations ({MAX_ITERATIONS}) reached without fully solving deficit."
            )

        return {
            "amount_managed": total_managed,
            "remaining_deficit": remaining_deficit,
        }

    def decide_deficit_action(self, deficit):
        """
        Decyduje o najlepszej akcji do podjęcia w celu zarządzania deficytem energii.

        Ta metoda analizuje aktualny stan systemu, w tym dostępność BESS i możliwość
        zakupu energii, aby wybrać najbardziej odpowiednią akcję do zarządzania deficytem.

        Argumenty:
            deficit (float): Aktualny deficyt energii w kW.

        Zwraca:
            DeficitAction: Wybrana akcja do wykonania.
        """
        if self.is_bess_available():
            bess_energy = self.microgrid.bess.get_charge_level()
            current_buy_price = self.osd.get_current_buy_price()
            print(f"OSD current buy price: {self.osd.get_current_buy_price()}")
            if self.should_discharge_bess(deficit, bess_energy, current_buy_price):
                return DeficitAction.DISCHARGE_BESS
        if self.can_buy_energy():
            return DeficitAction.BUY_ENERGY
        return DeficitAction.LIMIT_CONSUMPTION

    def execute_action(self, action, deficit):
        self.info_logger.info(f"Executing action: {action} for deficit: {deficit} kW")
        try:
            if action == DeficitAction.DISCHARGE_BESS:
                result = self.discharge_bess(deficit)
            elif action == DeficitAction.BUY_ENERGY:
                result = self.buy_energy(deficit)
            elif action == DeficitAction.LIMIT_CONSUMPTION:
                result = self.limit_consumption(deficit)
            else:
                raise ValueError(f"Unknown action: {action}")

            self.info_logger.info(f"Action result: {result}")
            return result
        except Exception as e:
            self.error_logger.error(f"Error executing action {action}: {str(e)}")
            return {"success": False, "amount": 0, "error": str(e)}

    def is_bess_available(self):

        return (
            self.microgrid.bess
            and self.microgrid.bess.get_switch_status()
            and self.microgrid.bess.get_charge_level() > 0
        )

    def can_buy_energy(self):
        result = self.osd.get_bought_power() < self.osd.get_purchase_limit()

        return result

    def discharge_bess(self, power_deficit):
        """
        Próbuje rozładować BESS w celu pokrycia deficytu.
        ZAKTUALIZOWANA: Używa BESSCapabilityChecker + planuje przyspieszoną iterację.
        
        Args:
            power_deficit: Deficyt mocy do pokrycia (kW)
            
        Returns:
            dict: Wynik operacji rozładowania
        """
        # Użyj capability checker jeśli dostępny
        if self.energy_manager_ref and self.energy_manager_ref.bess_checker:
            plan = self.energy_manager_ref.bess_checker.check_discharge_capability(power_deficit)
            
            # Log planu
            self.energy_manager_ref.bess_checker.log_plan(plan, "discharge")
            
            if not plan.is_feasible:
                return {
                    "success": False,
                    "amount": 0,
                    "percent": 0,
                    "reason": plan.reason
                }
            
            # Wykonaj rozładowanie
            bess = self.microgrid.bess
            discharged_amount, discharged_percent = bess.discharge(plan.power_setpoint)
            
            # Jeśli skończy się wcześniej - zaplanuj przyspieszoną iterację
            if plan.will_finish_before_next_iteration:
                self.energy_manager_ref.iteration_scheduler.schedule_early_iteration(
                    after_seconds=plan.time_to_completion_minutes * 60,
                    event_type="bess_discharge_complete",
                    description=f"BESS will be empty (discharged {plan.energy_amount:.2f} kWh)"
                )
            
            # Dodaj tracking zmian
            if self.energy_manager_ref:
                device_change = {
                    "device": bess,
                    "action": f"discharge:{discharged_amount}",
                    "new_value": discharged_amount,
                    "device_type": "BESS"
                }
                self.energy_manager_ref.changed_devices.append(device_change)
                self.info_logger.info(f"DEVICE CHANGED: {bess.name} (BESS) - discharge:{discharged_amount}")
            
            return {
                "success": True,
                "amount": discharged_amount,
                "percent": discharged_percent
            }
        
        # Fallback - stary kod (jeśli brak checkera)
        if not self.microgrid.bess:
            self.info_logger.warning("BESS is not available")
            return {"success": False, "amount": 0, "percent": 0}

        if not self.microgrid.bess.get_switch_status():
            self.info_logger.warning("BESS is not active")
            return {"success": False, "amount": 0, "percent": 0}

        self.info_logger.info(f"Attempting to discharge BESS by {power_deficit} kW")
        initial_charge = self.microgrid.bess.get_charge_level()

        discharged_amount, discharged_percent = self.microgrid.bess.discharge(
            power_deficit
        )

        if discharged_amount > 0:
            new_charge = self.microgrid.bess.get_charge_level()
            self.info_logger.info(
                f"BESS was discharged by {discharged_amount} kWh ({discharged_percent:.2f}%)"
            )
            self.info_logger.info(
                f"BESS charge level: before {initial_charge} kWh, after {new_charge} kWh"
            )
            
            # Dodaj tracking zmian
            if self.energy_manager_ref:
                device_change = {
                    "device": self.microgrid.bess,
                    "action": f"discharge:{discharged_amount}",
                    "new_value": discharged_amount,
                    "device_type": "BESS"
                }
                self.energy_manager_ref.changed_devices.append(device_change)
                self.info_logger.info(f"DEVICE CHANGED: {self.microgrid.bess.name} (BESS) - discharge:{discharged_amount}")
            
            return {
                "success": True,
                "amount": discharged_amount,
                "percent": discharged_percent,
            }
        else:
            self.info_logger.warning("Failed to discharge BESS")
            return {"success": False, "amount": 0, "percent": 0}

    def buy_energy(self, power_deficit):
        remaining_purchase_capacity = (
            self.osd.get_purchase_limit() - self.osd.get_bought_power()
        )
        amount_to_buy = min(power_deficit, remaining_purchase_capacity)
        if amount_to_buy > 0:
            self.osd.buy_power(amount_to_buy)
            # DODAJ TO - Śledzenie zmian OSD
            if self.energy_manager_ref:
                device_change = {
                    "device": self.osd,
                    "action": f"buy:{amount_to_buy}",
                    "new_value": amount_to_buy,
                    "device_type": "OSD"
                }
                self.energy_manager_ref.changed_devices.append(device_change)
                self.info_logger.info(f"DEVICE CHANGED: OSD (OSD) - buy:{amount_to_buy}")
            
            return {"success": True, "amount": amount_to_buy}
        return {"success": False, "amount": 0}

    def limit_consumption(self, power_deficit):
        """
        Ogranicza zużycie energii przez odbiorniki.
        
        ✅ ETAP 2: Z tracking poprzednich stanów.
        """
        self.info_logger.info(f"Attempting to limit consumption by {power_deficit} kW")
        total_reduced = 0
        devices_affected = []

        all_devices = (
            self.consumergrid.adjustable_devices
            + self.consumergrid.non_adjustable_devices
        )
        devices_by_priority = defaultdict(list)
        for device in all_devices:
            devices_by_priority[device.priority].append(device)

        sorted_priorities = sorted(devices_by_priority.keys())
        self.info_logger.info(f"Priorities to consider: {sorted_priorities}")

        for i, priority in enumerate(sorted_priorities):
            self.info_logger.info(f"\nConsidering priority {priority}")
            priority_devices = devices_by_priority[priority]
            total_power_in_priority = sum(
                self.get_reducible_power(d) for d in priority_devices if d.switch_status
            )
            self.info_logger.info(
                f"Total reducible power in priority {priority}: {total_power_in_priority} kW"
            )

            if total_power_in_priority >= power_deficit - total_reduced:
                self.info_logger.info(
                    f"Devices in priority {priority} can cover the remaining deficit"
                )
                priority_reduction = self.reduce_power_for_priority_group(
                    priority_devices, power_deficit - total_reduced
                )
                total_reduced += priority_reduction["amount"]
                devices_affected.extend(priority_reduction["devices"])
                self.info_logger.info(
                    f"Reduced {priority_reduction['amount']} kW from priority {priority}"
                )
                break
            else:
                next_priority = (
                    sorted_priorities[i + 1] if i + 1 < len(sorted_priorities) else None
                )
                if next_priority:
                    self.info_logger.info(
                        f"Checking for a single device in priority {next_priority}"
                    )
                    single_device = self.find_single_device_for_deficit(
                        devices_by_priority[next_priority],
                        power_deficit - total_reduced,
                    )
                    if single_device:
                        self.info_logger.info(
                            f"Found single device {single_device.name} in priority {next_priority}"
                        )
                        reduction = self.reduce_device_power(
                            single_device, power_deficit - total_reduced
                        )
                        total_reduced += reduction
                        devices_affected.append(
                            f"{single_device.name} reduced by {reduction} kW"
                        )
                        self.info_logger.info(
                            f"Reduced {reduction} kW from {single_device.name}"
                        )
                        break
                    else:
                        self.info_logger.info(
                            f"No single device found in priority {next_priority}"
                        )

                self.info_logger.info(
                    f"Reducing power from devices in priority {priority}"
                )
                priority_reduction = self.reduce_power_for_priority_group(
                    priority_devices, power_deficit - total_reduced
                )
                total_reduced += priority_reduction["amount"]
                devices_affected.extend(priority_reduction["devices"])
                self.info_logger.info(
                    f"Reduced {priority_reduction['amount']} kW from priority {priority}"
                )

            if total_reduced >= power_deficit:
                self.info_logger.info("Deficit fully covered")
                break

        remaining_deficit = max(0, power_deficit - total_reduced)
        self.info_logger.info(f"\nFinal results:")
        self.info_logger.info(f"Total power reduced: {total_reduced} kW")
        self.info_logger.info(f"Remaining deficit: {remaining_deficit} kW")

        if devices_affected:
            self.info_logger.info("Devices affected:")
            for device in devices_affected:
                self.info_logger.info(f"  - {device}")
        else:
            self.info_logger.warning(
                "No devices were affected during consumption limitation"
            )

        return {
            "success": total_reduced > 0,
            "amount": total_reduced,
            "remaining_deficit": remaining_deficit,
            "devices_affected": devices_affected,
        }

    def should_discharge_bess(self, deficit, bess_energy, current_buy_price):
        """
        Decyduje, czy rozładować System Magazynowania Energii w Akumulatorach (BESS).

        Ta metoda analizuje aktualny stan BESS, cenę zakupu energii i wielkość deficytu,
        aby zdecydować, czy rozładowanie BESS jest optymalną strategią.

        Argumenty:
            deficit (float): Aktualny deficyt energii w kW.
            bess_energy (float): Aktualny poziom energii w BESS w kWh.
            current_buy_price (float): Aktualna cena zakupu energii.

        Zwraca:
            bool: True jeśli BESS powinien być rozładowany, False w przeciwnym przypadku.
        """
        # Parametry do konfiguracji
        MIN_BUY_PRICE = 0.1
        MAX_BUY_PRICE = 0.5
        BESS_THRESHOLD = 20  # Minimalny poziom naładowania BESS (%)
        PRICE_THRESHOLD = 0.7
        HYSTERESIS = 0.05

        self.info_logger.info(
            "Start of the decision-making function concerning the discharge or purchase "
        )

        bess_percentage = (bess_energy / self.microgrid.bess.get_capacity()) * 100

        if bess_percentage <= BESS_THRESHOLD:
            self.info_logger.info(
                f"Purchase priority - low battery ({bess_percentage}%)"
            )
            return False

        price_factor = (current_buy_price - MIN_BUY_PRICE) / (
            MAX_BUY_PRICE - MIN_BUY_PRICE
        )

        # price_factor = max(0, min(price_factor, 1))
        # bess_factor = bess_percentage / 100

        price_factor = 0.6
        bess_factor = 0.8

        print("current", current_buy_price)
        print("priceFactor1", price_factor)
        print("bessFactor", bess_factor)

        if price_factor < PRICE_THRESHOLD and deficit < 50:
            decision = False  # Kupuj energię, gdy cena jest niska i deficyt mały
        elif price_factor > bess_factor + HYSTERESIS:
            decision = True  # Rozładuj baterię, gdy cena zakupu jest wysoka
        elif bess_factor > price_factor + HYSTERESIS:
            decision = True  # Rozładuj baterię, gdy poziom naładowania jest wysoki w stosunku do ceny
        else:
            decision = (
                self.previous_discharge_decision
            )  # Utrzymaj poprzednią decyzję w przypadku niezdecydowania

        self.previous_discharge_decision = decision
        return decision

    def get_proposed_actions(self, power_deficit):
        self.info_logger.info(
            f"[DEBUG] Proposing actions for deficit: {power_deficit} kW"
        )
        actions = []
        remaining_deficit = power_deficit

        # 1. Zwiększenie mocy aktywnych urządzeń
        increase_actions = self.prepare_increase_output_actions(remaining_deficit)
        actions.extend(increase_actions)
        remaining_deficit -= sum(action["reduction"] for action in increase_actions)

        # 2. Aktywacja nieaktywnych urządzeń
        if remaining_deficit > 0:
            activate_actions = self.prepare_activate_device_actions(remaining_deficit)
            actions.extend(activate_actions)
            remaining_deficit -= sum(action["reduction"] for action in activate_actions)

        # 3. Rozładowanie BESS lub zakup energii
        if remaining_deficit > 0:
            bess_available = self.is_bess_available()
            can_buy_energy = self.can_buy_energy()

            if bess_available and can_buy_energy:
                bess_energy = self.microgrid.bess.get_charge_level()
                current_buy_price = self.osd.get_current_buy_price()

                if self.should_discharge_bess(
                    remaining_deficit, bess_energy, current_buy_price
                ):
                    # Priorytet dla BESS
                    bess_action = self.prepare_bess_discharge_action(remaining_deficit)
                    if bess_action:
                        actions.append(bess_action)
                        remaining_deficit -= bess_action["reduction"]

                    if remaining_deficit > 0:
                        buy_action = self.prepare_buy_energy_action(remaining_deficit)
                        if buy_action:
                            actions.append(buy_action)
                            remaining_deficit -= buy_action["reduction"]
                else:
                    # Priorytet dla zakupu energii
                    buy_action = self.prepare_buy_energy_action(remaining_deficit)
                    if buy_action:
                        actions.append(buy_action)
                        remaining_deficit -= buy_action["reduction"]

                    if remaining_deficit > 0:
                        bess_action = self.prepare_bess_discharge_action(
                            remaining_deficit
                        )
                        if bess_action:
                            actions.append(bess_action)
                            remaining_deficit -= bess_action["reduction"]
            elif bess_available:
                bess_action = self.prepare_bess_discharge_action(remaining_deficit)
                if bess_action:
                    actions.append(bess_action)
                    remaining_deficit -= bess_action["reduction"]
            elif can_buy_energy:
                buy_action = self.prepare_buy_energy_action(remaining_deficit)
                if buy_action:
                    actions.append(buy_action)
                    remaining_deficit -= buy_action["reduction"]

        # 4. Ograniczenie zużycia jako ostateczność
        if remaining_deficit > 0:
            limit_actions = self.prepare_limit_consumption_actions(remaining_deficit)
            actions.extend(limit_actions)
            remaining_deficit -= sum(action["reduction"] for action in limit_actions)

        self.info_logger.info(f"[DEBUG] Proposed actions: {actions}")
        self.info_logger.info(
            f"[DEBUG] Remaining deficit after proposing actions: {remaining_deficit}"
        )
        return actions

    def prepare_buy_energy_action(self, power_deficit):
        remaining_purchase_capacity = (
            self.osd.get_purchase_limit() - self.osd.get_bought_power()
        )
        amount_to_buy = min(power_deficit, remaining_purchase_capacity)
        return {
            "id": str(uuid.uuid4()),
            "device_id": "OSD",
            "device_name": "OSD",
            "device_type": "OSD",
            "action": f"buy:{amount_to_buy}",
            "current_output": self.osd.get_bought_power(),
            "proposed_output": self.osd.get_bought_power() + amount_to_buy,
            "reduction": amount_to_buy,
        }

    def prepare_bess_discharge_action(self, power_deficit):
        self.info_logger.info(
            f"[DEBUG] Preparing BESS discharge action for deficit: {power_deficit}"
        )

        if not self.microgrid.bess or not self.microgrid.bess.get_switch_status():
            self.info_logger.info(
                "[DEBUG] BESS not available or not active for discharge action"
            )
            return None

        available_energy = self.microgrid.bess.get_available_energy()
        discharge_amount = min(power_deficit, available_energy)

        if discharge_amount <= 0:
            self.info_logger.info("[DEBUG] No energy available for discharge from BESS")
            return None

        action = {
            "id": str(uuid.uuid4()),
            "device_id": str(self.microgrid.bess.id),
            "device_name": self.microgrid.bess.name,
            "device_type": "BESS",
            "action": f"discharge:{discharge_amount:.2f}",
            "current_output": 0,
            "proposed_output": discharge_amount,
            "reduction": discharge_amount,
        }

        self.info_logger.info(f"[DEBUG] Prepared BESS action: {action}")
        return action

    def prepare_limit_consumption_actions(self, power_deficit):
        self.info_logger.info(
            f"[DEBUG] Preparing actions to limit consumption by {power_deficit} kW"
        )
        proposed_actions = []
        remaining_deficit = power_deficit

        all_devices = (
            self.consumergrid.adjustable_devices
            + self.consumergrid.non_adjustable_devices
        )
        devices_by_priority = defaultdict(list)
        for device in all_devices:
            devices_by_priority[device.priority].append(device)

        sorted_priorities = sorted(devices_by_priority.keys())
        self.info_logger.info(f"[DEBUG] Priorities to consider: {sorted_priorities}")

        for i, priority in enumerate(sorted_priorities):
            self.info_logger.info(f"[DEBUG] Considering priority {priority}")
            priority_devices = devices_by_priority[priority]
            total_power_in_priority = sum(
                self.get_reducible_power(d) for d in priority_devices if d.switch_status
            )
            self.info_logger.info(
                f"[DEBUG] Total reducible power in priority {priority}: {total_power_in_priority} kW"
            )

            if total_power_in_priority >= remaining_deficit:
                self.info_logger.info(
                    f"[DEBUG] Devices in priority {priority} can cover the remaining deficit"
                )
                proposed_actions.extend(
                    self.prepare_actions_for_priority_group(
                        priority_devices, remaining_deficit
                    )
                )
                break
            else:
                next_priority = (
                    sorted_priorities[i + 1] if i + 1 < len(sorted_priorities) else None
                )
                if next_priority:
                    self.info_logger.info(
                        f"[DEBUG] Checking for a single device in priority {next_priority}"
                    )
                    single_device = self.find_single_device_for_deficit(
                        devices_by_priority[next_priority], remaining_deficit
                    )
                    if single_device:
                        self.info_logger.info(
                            f"[DEBUG] Found single device {single_device.name} in priority {next_priority}"
                        )
                        proposed_actions.append(
                            self.prepare_action_for_device(
                                single_device, remaining_deficit
                            )
                        )
                        break
                    else:
                        self.info_logger.info(
                            f"[DEBUG] No single device found in priority {next_priority}"
                        )

                self.info_logger.info(
                    f"[DEBUG] Preparing actions for devices in priority {priority}"
                )
                priority_actions = self.prepare_actions_for_priority_group(
                    priority_devices, remaining_deficit
                )
                proposed_actions.extend(priority_actions)
                remaining_deficit -= sum(
                    action["reduction"] for action in priority_actions
                )

            if remaining_deficit <= 0:
                self.info_logger.info(
                    "[DEBUG] Deficit fully covered by proposed actions"
                )
                break

        self.info_logger.info(
            f"[DEBUG] Total proposed actions: {len(proposed_actions)}"
        )
        self.info_logger.info(
            f"[DEBUG] Remaining deficit after proposing actions: {remaining_deficit} kW"
        )
        return proposed_actions

    def prepare_increase_output_actions(self, power_deficit):
        actions = []
        remaining_deficit = power_deficit

        # Sortujemy aktywne urządzenia według priorytetu
        active_devices = sorted(
            self.microgrid.get_active_devices(), key=lambda x: x.priority
        )

        for device in active_devices:
            if remaining_deficit <= 0:
                break

            current_output = device.get_actual_output()
            max_output = device.get_max_output()

            if device.is_adjustable:
                new_output = min(max_output, current_output + remaining_deficit)
                increase = new_output - current_output
                if increase > 0:
                    actions.append(
                        {
                            "id": str(uuid.uuid4()),
                            "device_id": device.id,
                            "device_name": device.name,
                            "device_type": type(device).__name__,
                            "action": f"set_output:{new_output}",
                            "current_output": current_output,
                            "proposed_output": new_output,
                            "reduction": increase,
                        }
                    )
                    remaining_deficit -= increase
            else:
                # Dla urządzeń nieregulowanych, proponujemy tylko ustawienie na maksymalną moc, jeśli nie są już na niej
                if current_output < max_output:
                    increase = max_output - current_output
                    actions.append(
                        {
                            "id": str(uuid.uuid4()),
                            "device_id": device.id,
                            "device_name": device.name,
                            "device_type": type(device).__name__,
                            "action": f"set_output:{max_output}",
                            "current_output": current_output,
                            "proposed_output": max_output,
                            "reduction": increase,
                        }
                    )
                    remaining_deficit -= increase

        return actions

    def prepare_activate_device_actions(self, power_deficit):
        actions = []
        remaining_deficit = power_deficit

        # Sortujemy nieaktywne urządzenia według priorytetu
        inactive_devices = sorted(
            self.microgrid.get_inactive_devices(), key=lambda d: d.priority
        )

        for device in inactive_devices:
            if remaining_deficit <= 0:
                break

            max_output = device.get_max_output()
            if device.is_adjustable:
                proposed_output = min(max_output, remaining_deficit)
            else:
                proposed_output = max_output  # Dla nieregulowanych urządzeń zawsze proponujemy pełną moc

            actions.append(
                {
                    "id": str(uuid.uuid4()),
                    "device_id": device.id,
                    "device_name": device.name,
                    "device_type": type(device).__name__,
                    "action": f"activate_and_set:{proposed_output}",
                    "current_output": 0,
                    "proposed_output": proposed_output,
                    "reduction": proposed_output,
                }
            )

            remaining_deficit -= proposed_output

        return actions

    #############################

    def find_single_device_for_deficit(self, devices, deficit):
        for device in devices:
            if device.switch_status and self.get_reducible_power(device) >= deficit:
                return device
        return None

    def reduce_power_for_priority_group(self, devices, target_reduction):
        """
        Redukuje moc dla grupy urządzeń o tym samym priorytecie.
        
        ✅ ETAP 2: Z tracking poprzednich stanów.
        """
        total_reduced = 0
        devices_affected = []
        
        for device in devices:
            if not device.switch_status:
                continue
            
            if total_reduced >= target_reduction:
                break
            
            current_power = device.get_current_power()
            
            # ✅ ETAP 2: Zapisz stan PRZED ograniczeniem
            if self.energy_manager_ref:
                self.energy_manager_ref.save_device_state(device, "before_consumption_limit")
            
            # Dla urządzeń regulowanych
            if hasattr(device, 'min_power'):
                reducible = current_power - device.min_power
                reduction = min(reducible, target_reduction - total_reduced)
                
                if reduction > 0:
                    new_power = current_power - reduction
                    device.set_power(new_power)
                    
                    # ✅ ETAP 2: Dodaj do listy ograniczeń
                    if self.energy_manager_ref:
                        self.energy_manager_ref.add_artificial_limitation(
                            device=device,
                            limitation_type="consumption_limit",
                            original_power=current_power,
                            new_power=new_power,
                            was_active=True
                        )
                    
                    # Tracking zmian
                    if self.energy_manager_ref:
                        device_change = {
                            "device": device,
                            "action": f"reduce_power:{new_power:.2f}",
                            "previous_value": current_power,
                            "new_value": new_power,
                            "device_type": type(device).__name__
                        }
                        self.energy_manager_ref.changed_devices.append(device_change)
                    
                    total_reduced += reduction
                    devices_affected.append(f"{device.name} reduced by {reduction:.2f} kW")
            
            # Dla urządzeń nieregulowanych - tylko wyłączenie
            else:
                if current_power > 0:
                    # ✅ ETAP 2: Dodaj do listy ograniczeń PRZED wyłączeniem
                    if self.energy_manager_ref:
                        self.energy_manager_ref.add_artificial_limitation(
                            device=device,
                            limitation_type="consumption_limit",
                            original_power=current_power,
                            new_power=0,
                            was_active=True
                        )
                    
                    device.deactivate()
                    
                    # Tracking zmian
                    if self.energy_manager_ref:
                        device_change = {
                            "device": device,
                            "action": "turn_off",
                            "previous_value": current_power,
                            "new_value": 0,
                            "device_type": type(device).__name__
                        }
                        self.energy_manager_ref.changed_devices.append(device_change)
                    
                    total_reduced += current_power
                    devices_affected.append(f"{device.name} turned OFF (saved {current_power:.2f} kW)")
        
        return {
            "amount": total_reduced,
            "devices": devices_affected
        }

    def sorting_key(self, device, remaining_deficit):
        power_difference = abs(remaining_deficit - device.get_current_power())
        # Jeśli różnica mocy jest mniejsza niż 50% deficytu, preferuj urządzenia o większej mocy
        if power_difference < 0.5 * remaining_deficit:
            return (power_difference, -device.get_current_power())
        return (power_difference, 0)

    def reduce_device_power(self, device, target_reduction):
        """
        Redukuje moc pojedynczego urządzenia.
        
        ✅ ETAP 2: Z tracking poprzednich stanów.
        """
        current_power = device.get_current_power()
        
        # ✅ ETAP 2: Zapisz stan PRZED ograniczeniem
        if self.energy_manager_ref:
            self.energy_manager_ref.save_device_state(device, "before_consumption_limit")
        
        # Dla urządzeń regulowanych
        if hasattr(device, 'min_power'):
            reducible = current_power - device.min_power
            reduction = min(reducible, target_reduction)
            
            if reduction > 0:
                new_power = current_power - reduction
                device.set_power(new_power)
                
                # ✅ ETAP 2: Dodaj do listy ograniczeń
                if self.energy_manager_ref:
                    self.energy_manager_ref.add_artificial_limitation(
                        device=device,
                        limitation_type="consumption_limit",
                        original_power=current_power,
                        new_power=new_power,
                        was_active=True
                    )
                
                # Tracking zmian
                if self.energy_manager_ref:
                    device_change = {
                        "device": device,
                        "action": f"reduce_power:{new_power:.2f}",
                        "previous_value": current_power,
                        "new_value": new_power,
                        "device_type": type(device).__name__
                    }
                    self.energy_manager_ref.changed_devices.append(device_change)
                
                return reduction
        
        # Dla urządzeń nieregulowanych - wyłącz
        else:
            if current_power > 0:
                # ✅ ETAP 2: Dodaj do listy ograniczeń PRZED wyłączeniem
                if self.energy_manager_ref:
                    self.energy_manager_ref.add_artificial_limitation(
                        device=device,
                        limitation_type="consumption_limit",
                        original_power=current_power,
                        new_power=0,
                        was_active=True
                    )
                
                device.deactivate()
                
                # Tracking zmian
                if self.energy_manager_ref:
                    device_change = {
                        "device": device,
                        "action": "turn_off",
                        "previous_value": current_power,
                        "new_value": 0,
                        "device_type": type(device).__name__
                    }
                    self.energy_manager_ref.changed_devices.append(device_change)
                
                return current_power
        
        return 0

    def get_reducible_power(self, device):
        if not device.switch_status:
            return 0
        if isinstance(device, AdjustableDevice):
            return device.get_current_power() - device.min_power
        else:
            return device.get_current_power()

    ##########################

    def prepare_actions_for_priority_group(self, devices, target_reduction):
        proposed_actions = []
        total_reduction = 0

        self.info_logger.info(
            f"[DEBUG] Preparing actions to reduce {target_reduction} kW from priority group"
        )

        # Najpierw rozważ urządzenia regulowane
        adjustable_devices = [
            d for d in devices if isinstance(d, AdjustableDevice) and d.switch_status
        ]
        for device in adjustable_devices:
            self.info_logger.info(
                f"[DEBUG] Considering adjustable device: {device.name} (current power: {device.get_current_power()} kW)"
            )
            if total_reduction >= target_reduction:
                break
            action = self.prepare_action_for_device(
                device, target_reduction - total_reduction
            )
            if action:
                proposed_actions.append(action)
                total_reduction += action["reduction"]

        # Następnie rozważ urządzenia nieregulowane
        if total_reduction < target_reduction:
            non_adjustable_devices = [
                d
                for d in devices
                if not isinstance(d, AdjustableDevice) and d.switch_status
            ]
            sorted_non_adjustable = sorted(
                non_adjustable_devices,
                key=lambda d: self.sorting_key(d, target_reduction - total_reduction),
            )

            for device in sorted_non_adjustable:
                self.info_logger.info(
                    f"[DEBUG] Considering non-adjustable device: {device.name} (current power: {device.get_current_power()} kW)"
                )
                if total_reduction >= target_reduction:
                    break
                action = self.prepare_action_for_device(
                    device, target_reduction - total_reduction
                )
                if action:
                    proposed_actions.append(action)
                    total_reduction += action["reduction"]

        self.info_logger.info(
            f"[DEBUG] Total reduction proposed for priority group: {total_reduction} kW"
        )
        return proposed_actions

    def prepare_action_for_device(self, device, target_reduction):
        if isinstance(device, AdjustableDevice):
            max_reduction = device.get_current_power() - device.min_power
            reduction = min(max_reduction, target_reduction)
            if reduction > 0:
                return {
                    "id": str(uuid.uuid4()),
                    "device_id": device.id,
                    "device_name": device.name,
                    "device_type": type(device).__name__,
                    "action": f"reduce:{reduction}",
                    "current_output": device.get_current_power(),
                    "proposed_output": device.get_current_power() - reduction,
                    "reduction": reduction,
                }
        else:  # NonAdjustableDevice
            if device.get_current_power() > 0:
                return {
                    "id": str(uuid.uuid4()),
                    "device_id": device.id,
                    "device_name": device.name,
                    "device_type": type(device).__name__,
                    "action": "deactivate",
                    "current_output": device.get_current_power(),
                    "proposed_output": 0,
                    "reduction": device.get_current_power(),
                }
        return None
    
    def _load_decision_config(self) -> DecisionConfig:
        try:
            # Pobierz tryb z OSD (przychodzi z API jako 'energy_mode')
            mode_str = getattr(self.osd, 'energy_mode', 'AUTO').upper()
            
            if mode_str in DecisionMode.__members__:
                mode = DecisionMode[mode_str]
            else:
                self.error_logger.warning(f"Unknown energy_mode '{mode_str}', using AUTO")
                mode = DecisionMode.AUTO
            
            config = DecisionConfig(mode=mode)
            
            #self.info_logger.info(f"Decision config loaded: mode={config.mode.value}")
            
            return config
            
        except Exception as e:
            self.error_logger.error(f"Error loading decision config: {e}")
            return DecisionConfig()


    """
    POPRAWIONA FUNKCJA DEFICYTU - deficit_manager.py
    Spójna struktura z surplus_manager.py
    """

    def handle_deficit_both_action(self, power_deficit):
        """
        Obsługuje deficyt - rozładowanie BESS i/lub zakup z grid.
        
        STRUKTURA IDENTYCZNA JAK W SURPLUS:
        1. Sprawdź fizyczne możliwości (BESSCapabilityChecker)
        2. Jeśli obie opcje dostępne → Decyzja (utility function)
        3. Wykonaj wybraną akcję
        
        ✅ WSZYSTKIE REGUŁY BEZPIECZEŃSTWA SĄ W KROKU 1!
        
        Args:
            power_deficit: Deficyt mocy do pokrycia (kW)
            
        Returns:
            dict: Wynik operacji
        """
        bess = self.microgrid.bess
        
        self.info_logger.info(f"Deficit decision: {power_deficit:.2f} kW")
        
        # === KROK 1: SPRAWDŹ FIZYCZNE MOŻLIWOŚCI ===
        
        # 1A. Czy BESS może rozładować?
        can_discharge = False
        discharge_plan = None
        
        if self.energy_manager_ref and self.energy_manager_ref.bess_checker:
            bess = self.energy_manager_ref.microgrid.bess
            
            # ✅ ETAP 1: Sprawdź czy BESS już nie rozładowuje się!
            is_already_discharging, discharge_amount = self.energy_manager_ref.check_device_already_operating(
                "BESS", "discharging"
            )
            
            if is_already_discharging:
                self.info_logger.warning(
                    f"⚠️  BESS is ALREADY DISCHARGING {discharge_amount:.2f} kW - cannot discharge more"
                )
                can_discharge = False
            else:
                # Sprawdź fizyczne możliwości rozładowania
                discharge_plan = self.energy_manager_ref.bess_checker.check_discharge_capability(power_deficit)
                can_discharge = discharge_plan.is_feasible
                
                if can_discharge:
                    # ✅ BEZPIECZNY LOG - wszystkie pola mogą być None
                    self.info_logger.info(
                        f"✓ BESS can DISCHARGE: {discharge_plan.energy_amount:.2f} kWh "
                        f"at {abs(discharge_plan.power_setpoint):.2f} kW"
                    )
                    
                    # Opcjonalnie: log duration jeśli dostępny
                    if discharge_plan.time_to_completion_minutes is not None:
                        self.info_logger.info(
                            f"  → Duration: {discharge_plan.time_to_completion_minutes:.2f} min"
                        )
                else:
                    self.info_logger.info(
                        f"✗ BESS cannot discharge: {discharge_plan.reason}"
                    )
        else:
            self.info_logger.warning("BESS checker not available")
        
        # 1B. Czy Grid może importować?
        can_buy = self.osd.can_buy_energy()
        
        if can_buy:
            # ✅ ETAP 1: Sprawdź czy Grid już nie importuje!
            is_already_importing, import_amount = self.energy_manager_ref.check_device_already_operating(
                "GRID", "importing"
            )
            
            if is_already_importing:
                self.info_logger.warning(
                    f"⚠️  GRID is ALREADY IMPORTING {import_amount:.2f} kW - cannot import more"
                )
                can_buy = False
            else:
                remaining_capacity = self.osd.get_remaining_purchase_capacity()
                self.info_logger.info(
                    f"✓ GRID can BUY: {remaining_capacity:.2f} kWh remaining capacity"
                )
        
        # === KROK 2: PODEJMIJ DECYZJĘ ===
        
        # Przypadek A: Tylko DISCHARGE możliwe
        if can_discharge and not can_buy:
            self.info_logger.info("⚡ Only DISCHARGE available → discharging")
            return self._execute_discharge(discharge_plan, power_deficit)
        
        # Przypadek B: Tylko BUY możliwe
        if can_buy and not can_discharge:
            self.info_logger.info("💰 Only BUY available → buying")
            return self._execute_buy(power_deficit)
        
        # Przypadek C: Obie opcje dostępne → DECYZJA
        if can_discharge and can_buy:
            self.info_logger.info("⚖️  Both DISCHARGE and BUY available → making decision")
            
            # WYWOŁAJ FUNKCJĘ DECYZYJNĄ
            result = should_prioritize_discharging_or_buying(
                # BESS
                charge_level=bess.charge_level,
                min_charge_level=bess.min_charge_level,
                max_charge_level=bess.max_charge_level,
                
                # Sieć
                tariff_buy=self.osd.current_tariff_buy,
                tariff_sell=self.osd.current_tariff_sell,
                bought_power=self.osd.bought_power,
                purchase_limit=self.osd.CONTRACTED_PURCHASE_LIMIT,
                
                # Konfiguracja (ta sama co dla nadwyżki!)
                config=self.decision_config,
                
                # Logger
                info_logger=self.info_logger,
                error_logger=self.error_logger
            )
            
            # Loguj wynik
            self.info_logger.info(f"Decision: {result.reason}")
            self.info_logger.info(f"Confidence: {result.confidence*100:.1f}%")
            
            # Wykonaj decyzję
            if result.decision:  # DISCHARGE
                return self._execute_discharge(discharge_plan, power_deficit)
            else:  # BUY
                return self._execute_buy(power_deficit)
        
        # Przypadek D: Żadna opcja niedostępna
        self.info_logger.warning("⚠️  Neither DISCHARGE nor BUY available")
        return {"success": False, "amount": 0, "reason": "No action possible"}


    def _execute_discharge(self, discharge_plan, power_deficit):
        """
        Wykonuje rozładowanie BESS zgodnie z planem.
        
        STRUKTURA IDENTYCZNA JAK _execute_charge() W SURPLUS!
        
        Args:
            discharge_plan: BESSOperationPlan z BESSCapabilityChecker (lub None dla fallback)
            power_deficit: Deficyt do pokrycia (kW)
            
        Returns:
            dict: Wynik operacji rozładowania
        """
        bess = self.microgrid.bess
        
        # Użyj planu jeśli dostępny, inaczej fallback
        if discharge_plan:
            discharge_power = discharge_plan.power_setpoint
            self.info_logger.info(f"Executing DISCHARGE (with plan): {discharge_power:.2f} kW")
        else:
            # Fallback - użyj pełnego deficytu (discharge() i tak ogranicy)
            discharge_power = power_deficit
            self.info_logger.info(f"Executing DISCHARGE (fallback): {discharge_power:.2f} kW")
        
        # Wykonaj rozładowanie
        discharged_amount, discharged_percent = bess.discharge(discharge_power)
        
        self.info_logger.info(
            f"BESS discharged: {discharged_amount:.2f} kWh ({discharged_percent:.2f}%). "
            f"New level: {bess.charge_level:.2f} kWh"
        )
        
        # Tracking zmian
        if self.energy_manager_ref:
            device_change = {
                "device": bess,
                "action": f"discharge:{discharged_amount}",
                "new_value": discharged_amount,
                "device_type": "BESS"
            }
            self.energy_manager_ref.changed_devices.append(device_change)
            self.info_logger.info(f"DEVICE CHANGED: {bess.name} (BESS) - discharge:{discharged_amount:.2f}")
        
        # === EARLY ITERATION HANDLING ===
        if discharge_plan and discharge_plan.will_finish_before_next_iteration and self.energy_manager_ref:
            # BESS skończy wcześniej → zaplanuj early iteration
            self.energy_manager_ref.iteration_scheduler.schedule_early_iteration(
                after_seconds=discharge_plan.time_to_completion_minutes * 60,
                event_type="bess_discharge_complete",
                description=f"BESS will be empty (discharged {discharge_plan.energy_amount:.2f} kWh)"
            )
            
            self.info_logger.info(
                f"⏰ Early iteration scheduled in {discharge_plan.time_to_completion_minutes:.2f} min. "
                f"BESS setpoint will be set to 0 kW at that time. "
                f"Remaining deficit will be handled then."
            )
            
            # ✅ NIE kupuj reszty teraz - poczekaj na early iteration

        else:
            # BESS NIE skończy wcześniej → próbuj kupić resztę teraz
            if discharged_amount < power_deficit - self.EPSILON:
                remaining = power_deficit - discharged_amount
                self.info_logger.info(
                    f"Discharged {discharged_amount:.2f} kW, {remaining:.2f} kW remains. "
                    f"BESS won't finish early - attempting to buy remaining now."
                )
                
                # Sprawdź czy buy możliwe
                if self.can_buy_energy():
                    remaining_limit = self.osd.CONTRACTED_PURCHASE_LIMIT - self.osd.bought_power
                    if remaining_limit > self.EPSILON:
                        buy_result = self._execute_buy(remaining)
                        return {
                            "success": True,
                            "amount": discharged_amount + buy_result.get("amount", 0),
                            "percent": discharged_percent
                        }
                    else:
                        self.info_logger.warning("Cannot buy remaining - limit reached")
                else:
                    self.info_logger.warning("Cannot buy remaining - purchase not permitted")
        
        return {
            "success": True,
            "amount": discharged_amount,
            "percent": discharged_percent
        }


    def _execute_buy(self, amount):
        """
        Wykonuje zakup energii z grid.
        
        STRUKTURA IDENTYCZNA JAK _execute_sell() W SURPLUS!
        
        Args:
            amount: Ilość energii do zakupu (kW)
            
        Returns:
            dict: Wynik operacji zakupu
        """
        self.info_logger.info(f"Executing BUY: {amount:.2f} kW")
        
        # Ogranicz do dostępnego limitu
        remaining_limit = self.osd.CONTRACTED_PURCHASE_LIMIT - self.osd.bought_power
        amount_to_buy = min(amount, remaining_limit)
        
        if amount_to_buy <= self.EPSILON:
            self.info_logger.warning("Cannot buy - purchase limit reached")
            return {
                "success": False,
                "amount": 0,
                "reason": "Purchase limit reached"
            }
        
        # Kup energię z grid
        bought_amount = self.osd.buy_power(amount_to_buy)
        
        if bought_amount > 0:
            self.info_logger.info(f"Bought {bought_amount:.2f} kW from grid successfully")
            
            # Tracking zmian
            if self.energy_manager_ref:
                device_change = {
                    "device": self.osd,
                    "action": f"buy:{bought_amount}",
                    "new_value": bought_amount,
                    "device_type": "OSD"
                }
                self.energy_manager_ref.changed_devices.append(device_change)
                self.info_logger.info(f"DEVICE CHANGED: OSD - buy:{bought_amount:.2f}")
            
            return {
                "success": True,
                "amount": bought_amount
            }
        else:
            self.info_logger.warning("Failed to buy energy from grid")
            return {
                "success": False,
                "amount": 0,
                "reason": "Failed to buy from grid"
            }


    