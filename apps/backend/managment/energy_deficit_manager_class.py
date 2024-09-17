import uuid
from collections import defaultdict

from apps.backend.managment.deficit_action import DeficitAction
from apps.backend.devices.adjustable_devices import AdjustableDevice
from apps.backend.devices.non_adjustable import NonAdjustableDevice


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
        self.info_logger.info(f"Start managing power deficit:: {power_deficit} kW")

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
            if current_output + increased_power >= target_output:
                break

            if device.get_switch_status():  # Jeśli urządzenie jest aktywne
                initial_output = device.get_actual_output()
                max_output = device.get_max_output()

                if device.is_adjustable:
                    new_output = min(
                        max_output,
                        target_output
                        - (current_output + increased_power)
                        + initial_output,
                    )
                    if device.set_output(new_output):
                        actual_increase = new_output - initial_output
                        increased_power += actual_increase
                        self.info_logger.info(
                            f"Increased power of adjustable device {device.name} "
                            f"(priority: {device.priority}) from {initial_output} kW to {new_output} kW"
                        )
                else:
                    # Dla nieregulowanych urządzeń, sprawdzamy czy są już na maksimum
                    if initial_output < max_output:
                        if device.set_output(max_output):
                            actual_increase = max_output - initial_output
                            increased_power += actual_increase
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
                            new_output = min(
                                max_output,
                                target_output - (current_output + increased_power),
                            )
                            if device.set_output(new_output):
                                actual_increase = new_output
                                increased_power += actual_increase
                                self.info_logger.info(
                                    f"Activated adjustable device {device.name} "
                                    f"(priority: {device.priority}) and set power to {new_output} kW"
                                )
                        else:
                            # Dla nieregulowanych urządzeń, aktywujemy je na pełną moc
                            actual_increase = max_output
                            increased_power += actual_increase
                            self.info_logger.info(
                                f"Activated non-adjustable device {device.name} "
                                f"(priority: {device.priority}) at maximum power: {max_output} kW"
                            )

        self.info_logger.info(f"In total, power was increased by {increased_power} kW")
        self.info_logger.info(f"Final output: {current_output + increased_power} kW")
        return increased_power

    def manage_remaining_deficit(self, remaining_deficit):
        """
        Zarządza pozostałym deficytem energii po maksymalizacji produkcji.

        Ta metoda wykonuje serię działań w celu pokrycia pozostałego deficytu,
        w tym rozładowywanie BESS, zakup energii i ograniczanie zużycia.

        Argumenty:
            remaining_deficit (float): Pozostały deficyt energii do zarządzania w kW.

        Zwraca:
            dict: Słownik zawierający ilość zarządzonego deficytu i ewentualny pozostały deficyt.
        """
        total_managed = 0
        iteration = 0
        MAX_ITERATIONS = 100

        while remaining_deficit > 0 and iteration < MAX_ITERATIONS:
            iteration += 1
            self.info_logger.info(
                f"Iteration {iteration}, remaining deficit: {remaining_deficit} kW"
            )

            bess_available = self.is_bess_available()
            can_buy_energy = self.can_buy_energy()

            if bess_available and can_buy_energy:
                bess_energy = self.microgrid.bess.get_charge_level()
                current_buy_price = self.osd.get_current_buy_price()

                primary_action = self.decide_deficit_action(remaining_deficit)
                secondary_action = (
                    DeficitAction.DISCHARGE_BESS
                    if primary_action == DeficitAction.BUY_ENERGY
                    else DeficitAction.BUY_ENERGY
                )

                # Wykonaj pierwszą akcję
                result = self.execute_action(primary_action, remaining_deficit)
                if result["success"]:
                    total_managed += result["amount"]
                    remaining_deficit -= result["amount"]
                    self.info_logger.info(
                        f"Primary action {primary_action} managed {result['amount']} kW. Remaining deficit: {remaining_deficit} kW"
                    )

                # Jeśli nadal jest deficyt, wykonaj drugą akcję
                if remaining_deficit > 0:
                    result = self.execute_action(secondary_action, remaining_deficit)
                    if result["success"]:
                        total_managed += result["amount"]
                        remaining_deficit -= result["amount"]
                        self.info_logger.info(
                            f"Secondary action {secondary_action} managed {result['amount']} kW. Remaining deficit: {remaining_deficit} kW"
                        )

            elif bess_available:
                result = self.execute_action(
                    DeficitAction.DISCHARGE_BESS, remaining_deficit
                )
                if result["success"]:
                    total_managed += result["amount"]
                    remaining_deficit -= result["amount"]
                    self.info_logger.info(
                        f"BESS discharge managed {result['amount']} kW. Remaining deficit: {remaining_deficit} kW"
                    )

            elif can_buy_energy:
                result = self.execute_action(
                    DeficitAction.BUY_ENERGY, remaining_deficit
                )
                if result["success"]:
                    total_managed += result["amount"]
                    remaining_deficit -= result["amount"]
                    self.info_logger.info(
                        f"Energy purchase managed {result['amount']} kW. Remaining deficit: {remaining_deficit} kW"
                    )

            else:
                # Tylko jeśli nie można ani rozładować BESS, ani kupić energii, próbujemy ograniczyć zużycie
                result = self.execute_action(
                    DeficitAction.LIMIT_CONSUMPTION, remaining_deficit
                )
                if result["success"]:
                    total_managed += result["amount"]
                    remaining_deficit -= result["amount"]
                    self.info_logger.info(
                        f"Consumption limitation managed {result['amount']} kW. Remaining deficit: {remaining_deficit} kW"
                    )
                    if "devices_affected" in result:
                        for device in result["devices_affected"]:
                            self.info_logger.info(f"  - {device}")
                else:
                    self.info_logger.warning(
                        f"Failed to limit consumption. Reason: {result.get('error', 'Unknown')}"
                    )
                    if remaining_deficit == result.get(
                        "remaining_deficit", remaining_deficit
                    ):
                        self.info_logger.error(
                            "No further reduction possible. Exiting loop."
                        )
                        break

            self.info_logger.info(
                f"After iteration {iteration}: A total managed {total_managed} kW, remaining deficit {remaining_deficit} kW"
            )

        if iteration == MAX_ITERATIONS:
            self.error_logger.error(
                f"The maximum number of iterations ({MAX_ITERATIONS}) has been reached without fully solving the deficit."
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
        Próbuje rozładować System Magazynowania Energii w Akumulatorach (BESS) w celu pokrycia deficytu.

        Ta metoda sprawdza dostępność BESS i próbuje go rozładować, aby pokryć
        istniejący deficyt energii.

        Argumenty:
            power_deficit (float): Ilość deficytu energii do pokrycia w kW.

        Zwraca:
            dict: Słownik zawierający informacje o sukcesie operacji i ilości rozładowanej energii.
        """
        if self.microgrid.bess and self.microgrid.bess.get_switch_status():
            self.info_logger.info(f"Attempting to discharge BESS by {power_deficit} kW")
            initial_charge = self.microgrid.bess.get_charge_level()
            discharged = self.microgrid.bess.try_discharge(power_deficit)
            if discharged is not None:
                percent_discharged, amount_discharged = discharged
                new_charge = self.microgrid.bess.get_charge_level()
                self.info_logger.info(f"BESS was discharged by {amount_discharged} kWh")
                self.info_logger.info(
                    f"BESS charge level: before {initial_charge} kWh, after {new_charge} kWh"
                )
                return {"success": True, "amount": amount_discharged}
            else:
                self.info_logger.warning("Failure to discharge BESS")
        else:
            self.info_logger.warning("BESS is not available for discharge")
        return {"success": False, "amount": 0}

    def buy_energy(self, power_deficit):
        remaining_purchase_capacity = (
            self.osd.get_purchase_limit() - self.osd.get_bought_power()
        )
        amount_to_buy = min(power_deficit, remaining_purchase_capacity)
        if amount_to_buy > 0:
            self.osd.buy_power(amount_to_buy)
            return {"success": True, "amount": amount_to_buy}
        return {"success": False, "amount": 0}

    def limit_consumption(self, power_deficit):
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
        if self.microgrid.bess:
            available_energy = self.microgrid.bess.get_charge_level()
            discharge_amount = min(power_deficit, available_energy)
            action = {
                "id": str(uuid.uuid4()),
                "device_id": str(self.microgrid.bess.id),
                "device_name": self.microgrid.bess.name,
                "device_type": "BESS",
                "action": f"discharge:{discharge_amount}",
                "current_output": 0,
                "proposed_output": discharge_amount,
                "reduction": discharge_amount,
            }
            self.info_logger.info(f"[DEBUG] Prepared BESS action: {action}")
            return action
        else:
            self.info_logger.info("[DEBUG] BESS not available for discharge action")
        return None

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
        total_reduced = 0
        affected_devices = []

        self.info_logger.info(
            f"Attempting to reduce {target_reduction} kW from priority group"
        )

        # Najpierw rozważ urządzenia regulowane
        adjustable_devices = [
            d for d in devices if isinstance(d, AdjustableDevice) and d.switch_status
        ]
        for device in adjustable_devices:
            self.info_logger.info(
                f"Considering adjustable device: {device.name} (current power: {device.get_current_power()} kW)"
            )
            if total_reduced >= target_reduction:
                break
            reduction = self.reduce_device_power(
                device, target_reduction - total_reduced
            )
            if reduction > 0:
                total_reduced += reduction
                affected_devices.append(f"{device.name} reduced by {reduction} kW")
                self.info_logger.info(f"Reduced {reduction} kW from {device.name}")

        # Następnie rozważ urządzenia nieregulowane
        if total_reduced < target_reduction:
            non_adjustable_devices = [
                d
                for d in devices
                if not isinstance(d, AdjustableDevice) and d.switch_status
            ]

            sorted_non_adjustable = sorted(
                non_adjustable_devices,
                key=lambda d: self.sorting_key(d, target_reduction - total_reduced),
            )

            for device in sorted_non_adjustable:
                self.info_logger.info(
                    f"Considering non-adjustable device: {device.name} (current power: {device.get_current_power()} kW)"
                )
                if total_reduced >= target_reduction:
                    break
                reduction = self.reduce_device_power(
                    device, target_reduction - total_reduced
                )
                if reduction > 0:
                    total_reduced += reduction
                    affected_devices.append(f"{device.name} reduced by {reduction} kW")
                    self.info_logger.info(
                        f"Deactivated {device.name}, saved {reduction} kW"
                    )

        self.info_logger.info(f"Total reduced from priority group: {total_reduced} kW")
        return {"amount": total_reduced, "devices": affected_devices}

    def sorting_key(self, device, remaining_deficit):
        power_difference = abs(remaining_deficit - device.get_current_power())
        # Jeśli różnica mocy jest mniejsza niż 50% deficytu, preferuj urządzenia o większej mocy
        if power_difference < 0.5 * remaining_deficit:
            return (power_difference, -device.get_current_power())
        return (power_difference, 0)

    def reduce_device_power(self, device, target_reduction):
        initial_power = device.get_current_power()
        self.info_logger.info(
            f"Attempting to reduce {target_reduction} kW from {device.name} (current power: {initial_power} kW)"
        )

        if isinstance(device, AdjustableDevice):
            max_reduction = initial_power - device.min_power
            actual_reduction = min(max_reduction, target_reduction)
            device.decrease_power(actual_reduction)
            final_power = device.get_current_power()
            self.info_logger.info(
                f"Reduced {device.name} from {initial_power} kW to {final_power} kW"
            )
            return initial_power - final_power
        else:
            if device.deactivate():
                self.info_logger.info(
                    f"Deactivated {device.name}, saved {initial_power} kW"
                )
                return initial_power
            else:
                self.info_logger.warning(f"Failed to deactivate {device.name}")
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
