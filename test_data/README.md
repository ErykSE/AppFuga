# Test Scenarios for Energy Management System

## Overview
This directory contains realistic test scenarios based on the production `initial_data.json` and `contract_data.json`. Each scenario tests different edge cases and decision paths in the energy management algorithm.

## Test Scenarios

### Scenario 1: Small Deficit with BESS at Mid-Level
**File:** `scenario_1_small_deficit_bess_mid.json`

**Description:** Small deficit (~16 kW) with BESS at 50% capacity (can discharge up to 50 kW).

**Expected Behavior:**
- System should decide between BESS discharge vs Grid import
- Possible: Reduce adjustable loads (priority 3)
- BESS vs GRID decision based on utility function

**Test Coverage:** BESS discharge decision, small deficit handling

---

### Scenario 2: Small Surplus with BESS at Mid-Level
**File:** `scenario_2_small_surplus_bess_mid.json`

**Description:** Small surplus (~9 kW) with BESS at 50% capacity (can charge up to 40 kWh).

**Expected Behavior:**
- System should decide between BESS charge vs Grid export
- BESS vs GRID SELL decision based on utility function

**Test Coverage:** BESS charge decision, small surplus handling

---

### Scenario 3: Large Deficit Requiring Grid Import
**File:** `scenario_3_large_deficit_grid_required.json`

**Description:** Large deficit (~125 kW) with low generation and high consumption. BESS can discharge max 50 kW.

**Expected Behavior:**
- BESS discharge (max 50 kW)
- Grid import (remaining ~75 kW)
- Reduce adjustable loads (priority 3 first, then 2)
- Possible: Reduce priority 2 loads if still in deficit

**Test Coverage:** Multi-source deficit resolution, load reduction priorities

---

### Scenario 4: Large Surplus with Full BESS
**File:** `scenario_4_large_surplus_bess_full.json`

**Description:** Large surplus (~315 kW) with BESS at maximum capacity (90%).

**Expected Behavior:**
- BESS cannot charge (already at 90%)
- Grid export (sell energy)
- All surplus should go to grid

**Test Coverage:** BESS capacity limits, grid export handling

---

### Scenario 5: Balanced System
**File:** `scenario_5_balanced.json`

**Description:** Perfectly balanced system (generation = consumption).

**Expected Behavior:**
- No action required
- System should remain balanced

**Test Coverage:** Balanced state handling, no-action path

---

### Scenario 6: BESS Charging During Deficit (Conflict)
**File:** `scenario_6_bess_charging_during_deficit_conflict.json`

**Description:** BESS is charging (30 kW) during a deficit situation.

**Expected Behavior:**
- Stop BESS charging (neutralize conflict)
- BESS discharge decision (BESS vs GRID)
- Possible: Reduce adjustable loads

**Test Coverage:** Conflict detection and neutralization, BESS charging conflict

---

### Scenario 7: BESS Discharging During Surplus (Conflict)
**File:** `scenario_7_bess_discharging_during_surplus_conflict.json`

**Description:** BESS is discharging (25 kW) during a surplus situation.

**Expected Behavior:**
- Stop BESS discharging (neutralize conflict)
- BESS charge decision (BESS vs GRID SELL)
- Possible: Grid export if BESS not chosen

**Test Coverage:** Conflict detection and neutralization, BESS discharging conflict

---

### Scenario 8: BESS at Minimum Cannot Discharge
**File:** `scenario_8_bess_minimum_cannot_discharge.json`

**Description:** Large deficit (~125 kW) with BESS at minimum capacity (10%).

**Expected Behavior:**
- BESS cannot discharge (at minimum 10%)
- Grid import (full deficit)
- Reduce adjustable loads (priority 3 first, then 2)

**Test Coverage:** BESS minimum capacity limits, grid-only deficit resolution

---

### Scenario 9: Contract Limits Near Exhaustion
**File:** `scenario_9_contract_limits_exceeded.json`

**Description:** Large surplus (~305 kW) with BESS full and contract sale limit nearly exhausted (480/500 kWh).

**Expected Behavior:**
- BESS cannot charge (already at 90%)
- Grid export limited (only 20 kWh left in contract)
- Possible: Curtail generation if needed

**Test Coverage:** Contract limit handling, generation curtailment

---

## How to Use

### Running a Single Scenario
```bash
# Copy scenario data to production files
cp test_data/scenario_1_small_deficit_bess_mid.json apps/backend/initial_data.json
cp test_data/scenario_1_small_deficit_bess_mid.json apps/backend/contract_data.json

# Run the algorithm
python main_algorithm.py
```

### Running All Scenarios
Use the test runner:
```bash
python run_tests.py
```

## Test Coverage Matrix

| Scenario | Deficit | Surplus | BESS State | Grid | Loads | Conflict | Contract |
|----------|---------|---------|------------|------|-------|----------|----------|
| 1        | Small   | -       | Mid        | ✓    | ✓     | -        | -        |
| 2        | -       | Small   | Mid        | ✓    | -     | -        | -        |
| 3        | Large   | -       | Mid        | ✓    | ✓     | -        | -        |
| 4        | -       | Large   | Full       | ✓    | -     | -        | -        |
| 5        | -       | -       | Mid        | -    | -     | -        | -        |
| 6        | Small   | -       | Mid        | ✓    | ✓     | Charging | -        |
| 7        | -       | Small   | Mid        | ✓    | -     | Disch.   | -        |
| 8        | Large   | -       | Min        | ✓    | ✓     | -        | -        |
| 9        | -       | Large   | Full       | ✓    | -     | -        | Limit    |

## Data Structure

Each scenario file contains:
- `initial_data`: Device states (PV, Wind, BESS, Loads)
- `contract_data`: Contract parameters (limits, tariffs, mode)
- `expected_scenario`: Short description of expected behavior
- `expected_balance`: Expected energy balance in kW
- `expected_actions`: List of expected actions
- `description`: Detailed scenario description

## Notes

- All scenarios use realistic values based on production data
- BESS capacity: 100 kWh (10-90% usable range)
- BESS power: 50 kW max charge/discharge
- Contract limits: 500 kWh sale, 200 kWh purchase
- Tariffs: 0.35 PLN/kWh buy, 0.25 PLN/kWh sell
- Decision mode: AUTO (all scenarios)
