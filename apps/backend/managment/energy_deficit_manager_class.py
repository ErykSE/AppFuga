import uuid
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

                new_output = min(
                    max_output,
                    target_output - (current_output + increased_power) + initial_output,
                )

                device.set_output(new_output)
                actual_increase = new_output - initial_output
                increased_power += actual_increase

                self.info_logger.info(
                    f"Increased power of {device.name} (priority: {device.priority}) from {initial_output} kW to {new_output} kW"
                )

        # Jeśli nadal potrzebujemy więcej mocy, aktywujemy nieaktywne urządzenia
        if current_output + increased_power < target_output:
            for device in all_devices:
                if current_output + increased_power >= target_output:
                    break

                if not device.get_switch_status():  # Jeśli urządzenie jest nieaktywne
                    if device.try_activate():
                        max_output = device.get_max_output()
                        new_output = min(
                            max_output,
                            target_output - (current_output + increased_power),
                        )
                        device.set_output(new_output)
                        actual_increase = new_output
                        increased_power += actual_increase

                        self.info_logger.info(
                            f"Activated {device.name} (priority: {device.priority}) and set power to {new_output} kW"
                        )

        self.info_logger.info(f"In total, power was increased by {increased_power} kW")
        self.info_logger.info(f"Final output: {current_output + increased_power} kW")
        return increased_power

    """
    def adjust_power_output(self, target_power):

        current_power = self.microgrid.total_power_generated()
        power_difference = target_power - current_power
        step_size = min(
            abs(power_difference) * 0.2, 10
        )  # 20% różnicy lub 10 kW, cokolwiek jest mniejsze

        if power_difference > 0:
            return self.increase_power_gradually(power_difference, step_size)
        elif power_difference < 0:
            return self.decrease_power_gradually(-power_difference, step_size)
        else:
            self.info_logger.info("Power is already at an optimum level.")
            return 0
    

    def increase_power_gradually(self, power_deficit, step_size):
        
        self.info_logger.info(
            f"Gradual increase power. Deficit: {power_deficit} kW, Step: {step_size} kW"
        )
        increased_power = 0
        for device in self.microgrid.get_active_devices():
            if increased_power >= power_deficit:
                break
            if not device.is_at_max_output():
                current_output = device.get_actual_output()
                max_output = device.get_max_output()
                increase = min(
                    step_size,
                    max_output - current_output,
                    power_deficit - increased_power,
                )
                new_output = current_output + increase
                device.set_output(new_output)
                increased_power += increase
                self.info_logger.info(
                    f"Increased power {device.name} z {current_output} kW do {new_output} kW"
                )

        self.info_logger.info(f"In total, power was increased by {increased_power} kW")
        return increased_power

    def decrease_power_gradually(self, power_surplus, step_size):
        
        self.info_logger.info(
            f"Gradual reduction in power. Surplus: {power_surplus} kW, Step: {step_size} kW"
        )
        decreased_power = 0
        for device in reversed(
            self.microgrid.get_active_devices()
        ):  # Od najmniej priorytetowych
            if decreased_power >= power_surplus:
                break
            if device.get_actual_output() > device.get_min_output():
                current_output = device.get_actual_output()
                min_output = device.get_min_output()
                decrease = min(
                    step_size,
                    current_output - min_output,
                    power_surplus - decreased_power,
                )
                new_output = current_output - decrease
                device.set_output(new_output)
                decreased_power += decrease
                self.info_logger.info(
                    f"Reduced power {device.name} from {current_output} kW to {new_output} kW"
                )

        self.info_logger.info(f"In total, power was reduced by {decreased_power} kW")
        return decreased_power
    """

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

            action = self.decide_deficit_action(remaining_deficit)
            self.info_logger.info(f"Selected action: {action}")
            result = self.execute_action(action, remaining_deficit)

            if result["success"]:
                total_managed += result["amount"]
                remaining_deficit -= result["amount"]
                self.info_logger.info(
                    f"Action {action} managed {result['amount']} kW. Remaining deficit: {remaining_deficit} kW"
                )
            else:
                self.info_logger.warning(
                    f"Action {action} has failed. Reason: {result.get('error', 'Nieznany')}"
                )
                if action == DeficitAction.LIMIT_CONSUMPTION:
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
        if action == DeficitAction.DISCHARGE_BESS:
            return self.discharge_bess(deficit)
        elif action == DeficitAction.BUY_ENERGY:
            return self.buy_energy(deficit)
        elif action == DeficitAction.LIMIT_CONSUMPTION:
            return self.limit_consumption(deficit)
        else:
            raise ValueError(f"Unknown action: {action}")

    def is_bess_available(self):

        return (
            self.microgrid.bess
            and self.microgrid.bess.get_switch_status()
            and self.microgrid.bess.get_charge_level() > 0
        )

    def can_buy_energy(self):
        result = self.osd.get_bought_power() < self.osd.get_purchase_limit()

        return result

    """
    def increase_active_devices_output(self, power_deficit, can_handle_surplus):
        increased_power = 0
        for device in self.microgrid.get_active_devices():
            if not device.is_at_max_output():
                initial_output = device.get_actual_output()
                if can_handle_surplus:
                    increase = device.increase_output_to_full_capacity()
                else:
                    target_output = min(
                        initial_output + (power_deficit - increased_power),
                        device.get_max_output(),
                    )
                    device.set_output(target_output)
                    increase = device.get_actual_output() - initial_output
                increased_power += increase
                self.info_logger.info(
                    f"Increased device power {device.name} z {initial_output} kW to {device.get_actual_output()} kW"
                )
            if increased_power >= power_deficit and not can_handle_surplus:
                break
        self.info_logger.info(f"In total, power was increased by {increased_power} kW")
        return {"success": increased_power > 0, "amount": increased_power}

    """
    """
    def are_active_devices_at_full_capacity(self):
        active_devices = self.microgrid.get_active_devices()
        self.info_logger.info(f"Number of active devices: {len(active_devices)}")
        all_at_full_capacity = True
        for device in active_devices:
            current_output = device.get_actual_output()
            max_output = device.get_max_output()
            is_at_full = device.is_at_max_output()  # Zmiana tutaj
            self.info_logger.info(
                f"Device {device.name}: latest power {current_output} kW, maximum power {max_output} kW, at full power: {'Yes' if is_at_full else 'No'}"
            )
            all_at_full_capacity = all_at_full_capacity and is_at_full
        self.info_logger.info(
            f"All active equipment is operating at 100%: {'Yes' if all_at_full_capacity else 'No'}"
        )
        return all_at_full_capacity
    """

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
        """
        Ogranicza zużycie energii w celu pokrycia deficytu.

        Ta metoda redukuje moc urządzeń odbiorczych, zaczynając od
        urządzeń o najniższym priorytecie, aż do osiągnięcia wymaganej
        redukcji lub rozważenia wszystkich urządzeń.

        Argumenty:
            power_deficit (float): Ilość deficytu energii do pokrycia poprzez ograniczenie zużycia w kW.

        Zwraca:
            dict: Słownik zawierający informacje o sukcesie operacji,
                  ilości zredukowanej mocy i ewentualnym pozostałym deficycie.
        """
        self.info_logger.info(f"Attempting to limit consumption by {power_deficit} kW")
        total_reduced = 0

        all_devices = sorted(
            self.consumergrid.adjustable_devices
            + self.consumergrid.non_adjustable_devices,
            key=lambda x: (not isinstance(x, AdjustableDevice), x.priority),
        )

        for device in all_devices:
            if total_reduced >= power_deficit:
                break

            if isinstance(device, AdjustableDevice) and device.switch_status:
                reducible_power = device.power - device.min_power
                reduction_needed = min(reducible_power, power_deficit - total_reduced)
                if reduction_needed > 0:
                    actual_reduction = device.decrease_power(reduction_needed)
                    total_reduced += actual_reduction
                    self.info_logger.info(
                        f"Reduced {device.name} power by {actual_reduction} kW"
                    )

            elif isinstance(device, NonAdjustableDevice) and device.switch_status:
                if total_reduced + device.power <= power_deficit:
                    device.deactivate()
                    total_reduced += device.power
                    self.info_logger.info(
                        f"Deactivated {device.name}, saved {device.power} kW"
                    )

        remaining_deficit = power_deficit - total_reduced
        self.info_logger.info(f"Total power reduced: {total_reduced} kW")
        self.info_logger.info(f"Remaining deficit: {remaining_deficit} kW")

        return {
            "success": total_reduced > 0,
            "amount": total_reduced,
            "remaining_deficit": remaining_deficit,
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

    def activate_inactive_devices(self, power_deficit, can_handle_surplus):
        """
        Aktywuje nieaktywne urządzenia generujące w celu pokrycia deficytu energii.

        Ta metoda próbuje aktywować nieaktywne urządzenia generujące i ustawić ich
        moc wyjściową, aby pokryć istniejący deficyt energii.

        Argumenty:
            power_deficit (float): Ilość deficytu energii do pokrycia w kW.
            can_handle_surplus (bool): Czy system może obsłużyć ewentualną nadwyżkę energii.

        Zwraca:
            dict: Słownik zawierający informacje o sukcesie operacji i ilości aktywowanej mocy.
        """
        activated_power = 0
        for device in self.microgrid.get_inactive_devices():
            if device.try_activate():
                if can_handle_surplus:
                    increase = device.activate_and_set_to_full_capacity()
                else:
                    target_output = min(
                        power_deficit - activated_power, device.get_max_output()
                    )
                    device.set_output(target_output)
                    increase = device.get_actual_output()
                activated_power += increase
                self.info_logger.info(
                    f"The device {device.name} was activated and the power was increased by {increase} kW"
                )
            if activated_power >= power_deficit and not can_handle_surplus:
                break
        return {"success": activated_power > 0, "amount": activated_power}

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
            f"[DEBUG] Entering prepare_limit_consumption_actions with power_deficit: {power_deficit}"
        )
        actions = []
        remaining_deficit = power_deficit
        all_devices = sorted(
            self.consumergrid.adjustable_devices
            + self.consumergrid.non_adjustable_devices,
            key=lambda x: (not isinstance(x, AdjustableDevice), x.priority),
        )
        self.info_logger.info(f"[DEBUG] Total devices to consider: {len(all_devices)}")

        for device in all_devices:
            self.info_logger.info(
                f"[DEBUG] Considering device: ID={device.id}, Name={device.name}, Type={type(device).__name__}"
            )
            if remaining_deficit <= 0:
                self.info_logger.info(
                    "[DEBUG] Remaining deficit is 0 or less, breaking the loop"
                )
                break

            current_output = device.get_actual_output()
            if isinstance(device, AdjustableDevice):
                reducible_power = current_output - device.min_power
                reduction = min(reducible_power, remaining_deficit)
                self.info_logger.info(
                    f"[DEBUG] AdjustableDevice: Current output={current_output}, Min power={device.min_power}, Reducible power={reducible_power}, Proposed reduction={reduction}"
                )
                if reduction > 0:
                    action = {
                        "id": str(uuid.uuid4()),
                        "device_id": str(device.id),
                        "device_name": device.name,
                        "device_type": type(device).__name__,
                        "action": f"reduce:{reduction}",
                        "current_output": current_output,
                        "proposed_output": current_output - reduction,
                        "reduction": reduction,
                    }
                    actions.append(action)
                    self.info_logger.info(
                        f"[DEBUG] Created action for AdjustableDevice: {action}"
                    )
                    remaining_deficit -= reduction
            elif isinstance(device, NonAdjustableDevice):
                self.info_logger.info(
                    f"[DEBUG] NonAdjustableDevice: Current output={current_output}, Remaining deficit={remaining_deficit}"
                )
                if current_output > 0:
                    action = {
                        "id": str(uuid.uuid4()),
                        "device_id": str(device.id),
                        "device_name": device.name,
                        "device_type": type(device).__name__,
                        "action": "deactivate",
                        "current_output": current_output,
                        "proposed_output": 0,
                        "reduction": min(current_output, remaining_deficit),
                    }
                    actions.append(action)
                    self.info_logger.info(
                        f"[DEBUG] Created action for NonAdjustableDevice: {action}"
                    )
                    remaining_deficit -= min(current_output, remaining_deficit)

            self.info_logger.info(
                f"[DEBUG] After considering device, remaining deficit: {remaining_deficit}"
            )

        self.info_logger.info(
            f"[DEBUG] Exiting prepare_limit_consumption_actions. Total actions created: {len(actions)}, Remaining deficit: {remaining_deficit}"
        )
        return actions

    def prepare_increase_output_actions(self, power_deficit):
        actions = []
        for device in self.microgrid.get_active_devices():
            if device.get_actual_output() < device.get_max_output():
                increase = min(
                    device.get_max_output() - device.get_actual_output(), power_deficit
                )
                actions.append(
                    {
                        "id": str(uuid.uuid4()),
                        "device_id": device.id,
                        "device_name": device.name,
                        "device_type": type(device).__name__,
                        "action": f"increase:{increase}",
                        "current_output": device.get_actual_output(),
                        "proposed_output": device.get_actual_output() + increase,
                        "reduction": increase,
                    }
                )
        return actions

    def prepare_activate_device_actions(self, power_deficit):
        actions = []
        for device in self.microgrid.get_inactive_devices():
            if power_deficit > 0:
                actions.append(
                    {
                        "id": str(uuid.uuid4()),
                        "device_id": device.id,
                        "device_name": device.name,
                        "device_type": type(device).__name__,
                        "action": f"activate:{min(device.get_max_output(), power_deficit)}",
                        "current_output": 0,
                        "proposed_output": min(device.get_max_output(), power_deficit),
                        "reduction": min(device.get_max_output(), power_deficit),
                    }
                )
                power_deficit -= min(device.get_max_output(), power_deficit)
        return actions
