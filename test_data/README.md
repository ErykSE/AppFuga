# 🧪 Energy Management System - Test Scenarios

## 📋 Overview

This directory contains test scenarios for the Energy Management System. Each scenario tests different conditions and expected behaviors of the algorithm.

## 🎯 Test Scenarios

### 1. **Scenario 1: DEFICIT - BESS CHARGING CONFLICT**
- **File**: `scenario_1_deficit_bess_charging.json`
- **Description**: BESS is charging during a deficit (conflict)
- **Expected Balance**: -15.5 kW
- **Expected Actions**: Stop BESS charging, increase generation, BESS vs GRID decision
- **Test Focus**: Conflict neutralization

### 2. **Scenario 2: SURPLUS - BESS DISCHARGING CONFLICT**
- **File**: `scenario_2_surplus_bess_discharging.json`
- **Description**: BESS is discharging during a surplus (conflict)
- **Expected Balance**: +12.0 kW
- **Expected Actions**: Stop BESS discharging, BESS vs GRID decision
- **Test Focus**: Conflict neutralization

### 3. **Scenario 3: DEFICIT - BESS LOW CHARGE**
- **File**: `scenario_3_deficit_bess_low.json`
- **Description**: BESS has low charge, cannot discharge
- **Expected Balance**: -25.0 kW
- **Expected Actions**: Grid import or consumption limiting
- **Test Focus**: BESS limitations

### 4. **Scenario 4: SURPLUS - BESS FULL**
- **File**: `scenario_4_surplus_bess_full.json`
- **Description**: BESS is full, cannot charge
- **Expected Balance**: +20.0 kW
- **Expected Actions**: Grid export or generation limiting
- **Test Focus**: BESS limitations

### 5. **Scenario 5: BALANCED SYSTEM**
- **File**: `scenario_5_balanced.json`
- **Description**: System is balanced, no action needed
- **Expected Balance**: 0.0 kW
- **Expected Actions**: None
- **Test Focus**: Balanced state detection

### 6. **Scenario 6: EXTREME DEFICIT**
- **File**: `scenario_6_extreme_deficit.json`
- **Description**: Extreme deficit with limited options
- **Expected Balance**: -78.0 kW
- **Expected Actions**: Consumption limiting (last resort)
- **Test Focus**: Extreme conditions

### 7. **Scenario 7: EXTREME SURPLUS**
- **File**: `scenario_7_extreme_surplus.json`
- **Description**: Extreme surplus with limited options
- **Expected Balance**: +120.0 kW
- **Expected Actions**: Generation limiting (last resort)
- **Test Focus**: Extreme conditions

## 🚀 Running Tests

### Prerequisites
```bash
# Ensure you're in the project root directory
cd /path/to/AppFuga
```

### Run All Tests
```bash
python test_energy_management.py
```

### Run Individual Scenario
```python
from test_energy_management import TestEnergyManagement

tester = TestEnergyManagement()
tester.run_scenario("scenario_1_deficit_bess_charging.json")
```

## 📊 Test Results

The test script will:
1. ✅ Load each scenario
2. ✅ Calculate energy balance
3. ✅ Verify balance matches expectation
4. ✅ Simulate algorithm decision logic
5. ✅ Generate detailed report

### Expected Output
```
🧪 Testing scenario: scenario_1_deficit_bess_charging.json
============================================================
📋 Scenario: DEFICIT - BESS CHARGING CONFLICT
📝 Description: BESS ładuje się podczas deficytu - system powinien zatrzymać ładowanie i podjąć decyzję BESS vs GRID
⚖️  Expected Balance: -15.5 kW
📊 Calculated Balance: -15.50 kW
📈 Generation: 25.0 kW
📉 Consumption: 40.5 kW
🔋 BESS: -8.0 kW
✅ Balance calculation CORRECT

🤖 Algorithm Simulation:
   → DEFICIT detected - Managing deficit
```

## 📈 Success Criteria

- ✅ **Balance Calculation**: Actual balance matches expected within 0.1 kW
- ✅ **Decision Logic**: Correct deficit/surplus/balanced detection
- ✅ **Conflict Detection**: Proper identification of conflicting operations
- ✅ **Limitation Handling**: Correct handling of BESS/Grid limitations
- ✅ **Extreme Conditions**: Proper fallback to consumption/generation limiting

## 🔧 Customizing Tests

### Adding New Scenarios
1. Create new JSON file in `test_data/` directory
2. Follow the format of existing scenarios
3. Include `expected_scenario`, `expected_balance`, `expected_actions`, and `description`
4. Add to scenario list in `test_energy_management.py`

### Modifying Existing Scenarios
- Update device parameters in `initial_data`
- Modify contract limits in `contract_data`
- Adjust expected results accordingly

## 📄 Report Format

Test reports are saved as JSON files with timestamp:
```json
{
  "test_run": {
    "timestamp": "2024-01-15T14:30:25",
    "total_scenarios": 7,
    "passed": 7,
    "failed": 0
  },
  "scenarios": [
    {
      "scenario_file": "scenario_1_deficit_bess_charging.json",
      "expected_scenario": "DEFICIT - BESS CHARGING CONFLICT",
      "expected_balance": -15.5,
      "actual_balance": -15.5,
      "balance_match": true,
      "decision": "DEFICIT",
      "generation": 25.0,
      "consumption": 40.5,
      "bess_output": -8.0
    }
  ]
}
```

## 🎯 Integration with Main Algorithm

These test scenarios can be integrated with the main algorithm by:

1. **Loading scenario data** into the EnergyManager
2. **Running check_energy_conditions()** 
3. **Comparing results** with expected outcomes
4. **Validating log output** for correct decision reasoning

## 🚨 Troubleshooting

### Common Issues
- **File not found**: Ensure test_data directory exists
- **JSON parsing error**: Check JSON syntax in scenario files
- **Balance mismatch**: Verify calculation logic in test script
- **Import errors**: Check Python path and module structure

### Debug Mode
Add debug prints to see detailed calculations:
```python
print(f"Generation: {generation}")
print(f"Consumption: {consumption}")
print(f"BESS: {bess_output}")
print(f"Balance: {actual_balance}")
```
