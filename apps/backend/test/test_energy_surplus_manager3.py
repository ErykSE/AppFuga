import unittest
from unittest.mock import Mock, patch
from apps.backend.managment.energy_surplus_manager_class import EnergySurplusManager
from apps.backend.managment.surplus_action import SurplusAction


class TestEnergySurplusManager(unittest.TestCase):
    def setUp(self):
        # Mockowanie microgrid i osd
        self.microgrid = Mock()
        self.osd = Mock()

        # Mockowanie BESS units
        self.bess_units = [
            Mock(
                id=1,
                get_capacity=Mock(return_value=500),
                get_charge_level=Mock(return_value=200),
                get_switch_status=Mock(return_value=True),
                try_charge=Mock(return_value=(100, 100)),
            ),
            Mock(
                id=2,
                get_capacity=Mock(return_value=300),
                get_charge_level=Mock(return_value=150),
                get_switch_status=Mock(return_value=True),
                try_charge=Mock(return_value=(100, 100)),
            ),
        ]

        self.microgrid.bess_units.devices = self.bess_units

        # Ustawienie wartości zwracanych przez osd
        self.osd.get_contracted_export_possibility.return_value = True
        self.osd.get_sale_limit.return_value = 1000
        self.osd.get_sold_power.return_value = 0
        self.osd.get_contracted_sale_limit.return_value = 1000

        # Inicjalizacja EnergySurplusManager
        self.manager = EnergySurplusManager(self.microgrid, self.osd)

    def test_handle_surplus_both(self):
        self.osd.get_contracted_export_possibility.return_value = True
        action = self.manager.handle_surplus()
        self.assertEqual(action, SurplusAction.BOTH)
        print(f"Test handle_surplus (both): {action == SurplusAction.BOTH}")

    def test_handle_surplus_charge_battery(self):
        self.osd.get_contracted_export_possibility.return_value = False
        action = self.manager.handle_surplus()
        self.assertEqual(action, SurplusAction.CHARGE_BATTERY)
        print(
            f"Test handle_surplus (charge_battery): {action == SurplusAction.CHARGE_BATTERY}"
        )

    def test_handle_surplus_sell_energy(self):
        self.osd.get_contracted_export_possibility.return_value = True
        for bess in self.bess_units:
            bess.get_switch_status.return_value = False  # Wyłączanie BESS
        action = self.manager.handle_surplus()
        self.assertEqual(action, SurplusAction.SELL_ENERGY)
        print(
            f"Test handle_surplus (sell_energy): {action == SurplusAction.SELL_ENERGY}"
        )

    def test_handle_surplus_limit_generation(self):
        self.osd.get_contracted_export_possibility.return_value = False
        for bess in self.bess_units:
            bess.get_switch_status.return_value = False  # Wyłączanie BESS
        action = self.manager.handle_surplus()
        self.assertEqual(action, SurplusAction.LIMIT_GENERATION)
        print(
            f"Test handle_surplus (limit_generation): {action == SurplusAction.LIMIT_GENERATION}"
        )

    def test_handle_surplus_partial_bess(self):
        # Ustawienie eksportu na możliwy
        self.osd.get_contracted_export_possibility.return_value = True

        # Tylko jeden BESS jest dostępny do ładowania
        self.bess_units[0].get_switch_status.return_value = True
        self.bess_units[1].get_switch_status.return_value = False

        # Oczekiwana akcja to BOTH (ponieważ eksport i ładowanie są możliwe)
        action = self.manager.handle_surplus()
        self.assertEqual(action, SurplusAction.BOTH)
        print(f"Test handle_surplus (partial_bess): {action == SurplusAction.BOTH}")

    def test_handle_surplus_partial_export(self):
        # Ustawienie eksportu na możliwy
        self.osd.get_contracted_export_possibility.return_value = True

        # Ustawienie limitu sprzedaży na małą wartość
        self.osd.get_sale_limit.return_value = 10
        self.osd.get_sold_power.return_value = 5

        # Tylko część energii może być sprzedana
        action = self.manager.handle_surplus()
        self.assertEqual(action, SurplusAction.BOTH)
        print(f"Test handle_surplus (partial_export): {action == SurplusAction.BOTH}")

    def test_handle_surplus_no_bess_no_export(self):
        # Ustawienie eksportu na niemożliwy
        self.osd.get_contracted_export_possibility.return_value = False

        # Wyłączenie wszystkich BESS
        for bess in self.bess_units:
            bess.get_switch_status.return_value = False

        # Oczekiwana akcja to LIMIT_GENERATION
        action = self.manager.handle_surplus()
        self.assertEqual(action, SurplusAction.LIMIT_GENERATION)
        print(
            f"Test handle_surplus (no_bess_no_export): {action == SurplusAction.LIMIT_GENERATION}"
        )

    def test_manage_surplus_energy(self):
        self.osd.get_contracted_export_possibility.return_value = True
        power_surplus = 200
        result = self.manager.manage_surplus_energy(power_surplus)

        expected_action = SurplusAction.BOTH
        expected_amount_managed = 200
        expected_remaining_surplus = 0

        self.assertEqual(result["action"], expected_action)
        self.assertEqual(result["amount_managed"], expected_amount_managed)
        self.assertEqual(result["remaining_surplus"], expected_remaining_surplus)

        print(f"Test manage_surplus_energy:")
        print(f"  Action: {result['action'] == expected_action}")
        print(
            f"  Amount managed: {result['amount_managed'] == expected_amount_managed}"
        )
        print(
            f"  Remaining surplus: {result['remaining_surplus'] == expected_remaining_surplus}"
        )


if __name__ == "__main__":
    unittest.main()
