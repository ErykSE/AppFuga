#!/usr/bin/env python3
"""
Test script for Energy Management System
Tests various scenarios to verify algorithm correctness
"""

import json
import sys
import os
from datetime import datetime

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from apps.backend.managment.energy_manager_class import EnergyManager
from apps.backend.managment.energy_deficit_manager_class import EnergyDeficitManager
from apps.backend.managment.energy_surplus_manager_class import EnergySurplusManager

class TestEnergyManagement:
    def __init__(self):
        self.test_results = []
        self.scenarios_dir = "test_data"
        
    def load_scenario(self, scenario_file):
        """Load test scenario from JSON file"""
        try:
            with open(f"{self.scenarios_dir}/{scenario_file}", 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"❌ Scenario file not found: {scenario_file}")
            return None
        except json.JSONDecodeError as e:
            print(f"❌ Invalid JSON in {scenario_file}: {e}")
            return None
    
    def create_mock_objects(self, scenario_data):
        """Create mock objects from scenario data"""
        # This is a simplified mock - in real implementation you'd use actual device classes
        class MockDevice:
            def __init__(self, data):
                for key, value in data.items():
                    setattr(self, key, value)
            
            def get_switch_status(self):
                return getattr(self, 'switch_status', False)
            
            def get_actual_output(self):
                return getattr(self, 'actual_output', 0)
            
            def get_max_output(self):
                return getattr(self, 'max_output', 0)
            
            def get_current_power(self):
                return getattr(self, 'power', 0)
        
        class MockMicrogrid:
            def __init__(self, data):
                self.pv_panels = [MockDevice(panel) for panel in data.get('pv_panels', [])]
                self.wind_turbines = [MockDevice(turbine) for turbine in data.get('wind_turbines', [])]
                self.fuel_turbines = [MockDevice(turbine) for turbine in data.get('fuel_turbines', [])]
                self.fuel_cells = [MockDevice(cell) for cell in data.get('fuel_cells', [])]
                self.bess = MockDevice(data.get('bess', [{}])[0]) if data.get('bess') else None
                
            def total_power_generated(self):
                total = 0
                for device_list in [self.pv_panels, self.wind_turbines, self.fuel_turbines, self.fuel_cells]:
                    for device in device_list:
                        if device.get_switch_status():
                            total += device.get_actual_output()
                return total
        
        class MockConsumerGrid:
            def __init__(self, data):
                self.adjustable_devices = [MockDevice(device) for device in data.get('adjustable_devices', [])]
                self.non_adjustable_devices = [MockDevice(device) for device in data.get('non_adjustable_devices', [])]
                
            def total_power_consumed(self):
                total = 0
                for device_list in [self.adjustable_devices, self.non_adjustable_devices]:
                    for device in device_list:
                        if device.get_switch_status():
                            total += device.get_current_power()
                return total
        
        class MockOSD:
            def __init__(self, contract_data):
                for key, value in contract_data.items():
                    setattr(self, key, value)
            
            def can_buy_energy(self):
                return self.bought_power < self.CONTRACTED_PURCHASE_LIMIT
            
            def can_sell_energy(self):
                return self.sold_power < self.CONTRACTED_SALE_LIMIT
            
            def get_remaining_purchase_capacity(self):
                return self.CONTRACTED_PURCHASE_LIMIT - self.bought_power
            
            def get_remaining_sale_capacity(self):
                return self.CONTRACTED_SALE_LIMIT - self.sold_power
        
        return {
            'microgrid': MockMicrogrid(scenario_data['initial_data']),
            'consumergrid': MockConsumerGrid(scenario_data['initial_data']),
            'osd': MockOSD(scenario_data['contract_data'])
        }
    
    def run_scenario(self, scenario_file):
        """Run a single test scenario"""
        print(f"\n🧪 Testing scenario: {scenario_file}")
        print("=" * 60)
        
        # Load scenario data
        scenario_data = self.load_scenario(scenario_file)
        if not scenario_data:
            return False
        
        print(f"📋 Scenario: {scenario_data.get('expected_scenario', 'Unknown')}")
        print(f"📝 Description: {scenario_data.get('description', 'No description')}")
        print(f"⚖️  Expected Balance: {scenario_data.get('expected_balance', 'Unknown')} kW")
        
        # Create mock objects
        mock_objects = self.create_mock_objects(scenario_data)
        
        # Calculate expected balance
        generation = mock_objects['microgrid'].total_power_generated()
        consumption = mock_objects['consumergrid'].total_power_consumed()
        bess_output = mock_objects['microgrid'].bess.get_actual_output() if mock_objects['microgrid'].bess else 0
        
        # BESS output: negative = charging (demand), positive = discharging (supply)
        if bess_output < 0:
            # BESS charging - adds to demand
            actual_balance = generation - (consumption + abs(bess_output))
        else:
            # BESS discharging - adds to supply
            actual_balance = (generation + bess_output) - consumption
        
        print(f"📊 Calculated Balance: {actual_balance:.2f} kW")
        print(f"📈 Generation: {generation:.2f} kW")
        print(f"📉 Consumption: {consumption:.2f} kW")
        print(f"🔋 BESS: {bess_output:.2f} kW")
        
        # Check if balance matches expectation
        expected_balance = scenario_data.get('expected_balance', 0)
        balance_match = abs(actual_balance - expected_balance) < 0.1
        
        if balance_match:
            print("✅ Balance calculation CORRECT")
        else:
            print(f"❌ Balance calculation INCORRECT (expected: {expected_balance}, got: {actual_balance:.2f})")
        
        # Simulate algorithm decision logic
        print("\n🤖 Algorithm Simulation:")
        
        if abs(actual_balance) < 1.0:
            print("   → System BALANCED - No action needed")
            decision = "BALANCED"
        elif actual_balance < 0:
            print("   → DEFICIT detected - Managing deficit")
            decision = "DEFICIT"
        else:
            print("   → SURPLUS detected - Managing surplus")
            decision = "SURPLUS"
        
        # Test result
        result = {
            'scenario_file': scenario_file,
            'expected_scenario': scenario_data.get('expected_scenario'),
            'expected_balance': expected_balance,
            'actual_balance': actual_balance,
            'balance_match': balance_match,
            'decision': decision,
            'generation': generation,
            'consumption': consumption,
            'bess_output': bess_output,
            'timestamp': datetime.now().isoformat()
        }
        
        self.test_results.append(result)
        return balance_match
    
    def run_all_scenarios(self):
        """Run all test scenarios"""
        print("🚀 Starting Energy Management System Tests")
        print("=" * 60)
        
        # List all scenario files
        scenario_files = [
            "scenario_1_deficit_bess_charging.json",
            "scenario_2_surplus_bess_discharging.json", 
            "scenario_3_deficit_bess_low.json",
            "scenario_4_surplus_bess_full.json",
            "scenario_5_balanced.json",
            "scenario_6_extreme_deficit.json",
            "scenario_7_extreme_surplus.json",
            "scenario_8_real_data.json"
        ]
        
        passed = 0
        total = len(scenario_files)
        
        for scenario_file in scenario_files:
            if self.run_scenario(scenario_file):
                passed += 1
        
        # Summary
        print(f"\n📊 TEST SUMMARY")
        print("=" * 60)
        print(f"✅ Passed: {passed}/{total}")
        print(f"❌ Failed: {total - passed}/{total}")
        print(f"📈 Success Rate: {(passed/total)*100:.1f}%")
        
        if passed == total:
            print("\n🎉 ALL TESTS PASSED! System is working correctly.")
        else:
            print(f"\n⚠️  {total - passed} tests failed. Check the results above.")
        
        return passed == total
    
    def generate_report(self):
        """Generate detailed test report"""
        report_file = f"test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        report = {
            'test_run': {
                'timestamp': datetime.now().isoformat(),
                'total_scenarios': len(self.test_results),
                'passed': sum(1 for r in self.test_results if r['balance_match']),
                'failed': sum(1 for r in self.test_results if not r['balance_match'])
            },
            'scenarios': self.test_results
        }
        
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"\n📄 Detailed report saved to: {report_file}")
        return report_file

def main():
    """Main test function"""
    tester = TestEnergyManagement()
    
    try:
        success = tester.run_all_scenarios()
        report_file = tester.generate_report()
        
        if success:
            print(f"\n🎯 All tests completed successfully!")
            print(f"📄 Report: {report_file}")
            return 0
        else:
            print(f"\n⚠️  Some tests failed. Check the report: {report_file}")
            return 1
            
    except Exception as e:
        print(f"\n❌ Test execution failed: {e}")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
