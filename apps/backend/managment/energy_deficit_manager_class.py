from apps.backend.managment.deficit_action import DeficitAction

######################


class EnergyDeficitManager:
    """
    Klasa zarządzająca deficytem energii.
    """

    def __init__(self, microgrid, osd, info_logger, error_logger):
        self.microgrid = microgrid
        self.osd = osd
        self.info_logger = info_logger
        self.error_logger = error_logger
        self.previous_discharge_decision = False  # Domyślna wartość

    def handle_deficit(self, power_deficit):
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

    def can_handle_more_power(self, additional_power):
        bess_free_capacity = (
            self.microgrid.bess.get_capacity() - self.microgrid.bess.get_charge_level()
            if self.microgrid.bess
            else 0
        )
        sale_capacity = self.osd.get_remaining_sale_capacity()
        total_capacity = bess_free_capacity + sale_capacity

        # self.info_logger.info(f"Additional power required: {additional_power} kW")

        can_handle = total_capacity >= additional_power

        print(sale_capacity)
        print("total_capacity", total_capacity)
        print("additional_power", additional_power)
        print("can_handle", can_handle)
        # self.info_logger.info(
        # f"Can the system handle the additional power: {'Yes' if can_handle else 'No'}"
        # )

        return can_handle

    def maximize_power_output(self, power_deficit):

        can_handle_surplus = self.can_handle_more_power(power_deficit)

        self.info_logger.info(
            f"Can the system handle the additional power: {'Yes' if can_handle_surplus else 'No'}"
        )

        print("can_handle_surplus", can_handle_surplus)

        if can_handle_surplus:
            self.info_logger.info("Attempting to maximize output")
        else:
            self.info_logger.info("Attempting to control equipment to meet demand")

        increased_power = 0
        active_devices = self.microgrid.get_active_devices()
        self.info_logger.info(f"Liczba aktywnych urządzeń: {len(active_devices)}")

        for device in active_devices:
            initial_output = device.get_actual_output()
            max_output = device.get_max_output()

            if can_handle_surplus:
                increase = max_output - initial_output
            else:
                increase = min(
                    max_output - initial_output, power_deficit - increased_power
                )

            if increase > 0:
                device.set_output(initial_output + increase)
                new_output = device.get_actual_output()
                actual_increase = new_output - initial_output
                increased_power += actual_increase
                self.info_logger.info(
                    f"Increased power {device.name} from {initial_output} kW to {new_output} kW"
                )

            if increased_power >= power_deficit and not can_handle_surplus:
                break

        if can_handle_surplus or increased_power < power_deficit:
            inactive_devices = self.microgrid.get_inactive_devices()
            for device in inactive_devices:
                if device.try_activate():
                    if can_handle_surplus:
                        new_output = device.get_max_output()
                    else:
                        new_output = min(
                            device.get_max_output(), power_deficit - increased_power
                        )
                    device.set_output(new_output)
                    increased_power += new_output
                    self.info_logger.info(
                        f"Activated {device.name} and set the power to {new_output} kW"
                    )

                if increased_power >= power_deficit and not can_handle_surplus:
                    break

        self.info_logger.info(f"In total, power was increased by {increased_power} kW")
        return increased_power

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

    def manage_remaining_deficit(self, remaining_deficit):
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
        if self.is_bess_available():
            bess_energy = self.microgrid.bess.get_charge_level()
            current_buy_price = self.osd.get_current_buy_price()
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
            raise ValueError(f"Nieznana akcja: {action}")

    def is_bess_available(self):

        return (
            self.microgrid.bess
            and self.microgrid.bess.get_switch_status()
            and self.microgrid.bess.get_charge_level() > 0
        )

    def can_buy_energy(self):
        result = self.osd.get_bought_power() < self.osd.get_purchase_limit()

        return result

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
                    f"Zwiększono moc urządzenia {device.name} z {initial_output} kW do {device.get_actual_output()} kW"
                )
            if increased_power >= power_deficit and not can_handle_surplus:
                break
        self.info_logger.info(f"Łącznie zwiększono moc o {increased_power} kW")
        return {"success": increased_power > 0, "amount": increased_power}

    def are_active_devices_at_full_capacity(self):
        active_devices = self.microgrid.get_active_devices()
        self.info_logger.info(f"Liczba aktywnych urządzeń: {len(active_devices)}")
        all_at_full_capacity = True
        for device in active_devices:
            current_output = device.get_actual_output()
            max_output = device.get_max_output()
            is_at_full = device.is_at_max_output()  # Zmiana tutaj
            self.info_logger.info(
                f"Urządzenie {device.name}: aktualna moc {current_output} kW, maksymalna moc {max_output} kW, na pełnej mocy: {'Tak' if is_at_full else 'Nie'}"
            )
            all_at_full_capacity = all_at_full_capacity and is_at_full
        self.info_logger.info(
            f"Wszystkie aktywne urządzenia pracują na 100%: {'Tak' if all_at_full_capacity else 'Nie'}"
        )
        return all_at_full_capacity

    def discharge_bess(self, power_deficit):
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
        # Implementacja ograniczenia zużycia
        # To może wymagać dodatkowej logiki w zależności od specyfiki systemu
        self.info_logger.info(f"Limiting consumption by {power_deficit} kW")
        return {"success": True, "amount": power_deficit}

    def should_discharge_bess(self, deficit, bess_energy, current_buy_price):
        # Parametry do konfiguracji
        MIN_BUY_PRICE = 0.08
        MAX_BUY_PRICE = 0.18
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
        price_factor = 0.3
        bess_factor = bess_percentage / 100

        if price_factor < PRICE_THRESHOLD and deficit < 50:
            decision = False
            self.info_logger.info(
                f"Purchase priority: low price ({current_buy_price}) i niewielki deficyt ({deficit} kW)"
            )
        elif bess_factor > price_factor + HYSTERESIS:
            decision = True
            self.info_logger.info(
                f"Discharge BESS priority: bess factor ({bess_factor:.2f}) > price factor ({price_factor:.2f})"
            )
        elif price_factor > bess_factor + HYSTERESIS:
            decision = False
            self.info_logger.info(
                f"Purchase priority: price factor ({price_factor:.2f}) > bess factor ({bess_factor:.2f})"
            )
        else:
            decision = self.previous_discharge_decision
            self.info_logger.info(
                f"Behaviour of the previous decision: values within the hysteresis range"
            )

        self.previous_discharge_decision = decision
        return decision

    def activate_inactive_devices(self, power_deficit, can_handle_surplus):
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
                    f"Aktywowano urządzenie {device.name} i zwiększono moc o {increase} kW"
                )
            if activated_power >= power_deficit and not can_handle_surplus:
                break
        return {"success": activated_power > 0, "amount": activated_power}
