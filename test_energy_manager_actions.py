import json
import os
import time
import unittest
from unittest.mock import Mock, patch

from apps.backend.managment.energy_manager_class import EnergyManager
from apps.backend.managment.operation_action import OperationMode


class TestEnergyManagerActions(unittest.TestCase):
    def setUp(self):
        print("\n--- Setting up test ---")
        self.microgrid = Mock()
        self.consumergrid = Mock()
        self.osd = Mock()
        self.info_logger = Mock()
        self.error_logger = Mock()

        # Tworzymy tymczasowe pliki do testów
        self.pending_actions_path = "test_pending_actions.json"
        self.operator_decisions_path = "test_operator_decisions.json"

        self.energy_manager = EnergyManager(
            self.microgrid,
            self.consumergrid,
            self.osd,
            self.info_logger,
            self.error_logger,
        )
        self.energy_manager.pending_actions_path = self.pending_actions_path
        self.energy_manager.operator_decisions_path = self.operator_decisions_path
        self.energy_manager.operation_mode = OperationMode.SEMI_AUTOMATIC
        print("Energy Manager initialized")

    def tearDown(self):
        print("\n--- Cleaning up after test ---")
        # Usuwamy tymczasowe pliki po testach
        if os.path.exists(self.pending_actions_path):
            os.remove(self.pending_actions_path)
            print(f"Removed {self.pending_actions_path}")
        if os.path.exists(self.operator_decisions_path):
            os.remove(self.operator_decisions_path)
            print(f"Removed {self.operator_decisions_path}")

    @patch.object(EnergyManager, "perform_action")
    def test_action_flow(self, mock_perform_action):
        print("\n--- Starting test_action_flow ---")
        # 1. Dodajemy akcję
        device = Mock()
        device.id = 1
        device.name = "Test Device"
        action = "test_action"

        result = self.energy_manager.add_pending_action(device, action)
        self.assertTrue(result["success"])
        self.assertTrue(result["pending"])
        print(f"Added pending action: {result}")

        # Sprawdzamy, czy akcja została dodana do pliku
        with open(self.pending_actions_path, "r") as f:
            pending_actions = json.load(f)
        self.assertEqual(len(pending_actions), 1)
        self.assertEqual(pending_actions[0]["device_id"], 1)
        self.assertEqual(pending_actions[0]["action"], "test_action")
        print(f"Pending actions in file: {pending_actions}")

        # 2. Symulujemy odpowiedź operatora
        operator_decision = [
            {
                "device_id": 1,
                "device_name": "Test Device",
                "action": "test_action",
                "approved": True,
            }
        ]
        with open(self.operator_decisions_path, "w") as f:
            json.dump(operator_decision, f)
        print(f"Simulated operator decision: {operator_decision}")

        # 3. Przetwarzamy decyzje operatora
        mock_perform_action.return_value = {"success": True}
        self.energy_manager.process_operator_decisions()
        print("Processed operator decisions")

        # 4. Sprawdzamy, czy pliki zostały wyczyszczone
        with open(self.pending_actions_path, "r") as f:
            pending_actions = json.load(f)
        self.assertEqual(len(pending_actions), 0)
        print(f"Pending actions after processing: {pending_actions}")

        with open(self.operator_decisions_path, "r") as f:
            operator_decisions = json.load(f)
        self.assertEqual(len(operator_decisions), 0)
        print(f"Operator decisions after processing: {operator_decisions}")

        # 5. Sprawdzamy, czy akcja została wykonana
        mock_perform_action.assert_called_once()
        print("Verified that perform_action was called")


if __name__ == "__main__":
    unittest.main(verbosity=2)
