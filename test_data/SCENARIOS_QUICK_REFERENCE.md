# Szybka Referencja - Scenariusze Testowe

## 📋 Tabela Podsumowująca

| Plik | Bilans | BESS | Generatory | Główne Działanie | Testuje |
|------|--------|------|------------|------------------|---------|
| **scenario_1_small_deficit_bess_mid.json** | -15.8 kW | 50% | Max | BESS vs GRID | Mały deficyt, BESS discharge |
| **scenario_2_small_surplus_bess_mid.json** | +8.7 kW | 50% | Max | BESS vs GRID SELL | Mała nadwyżka, BESS charge |
| **scenario_3_large_deficit_grid_required.json** | -125 kW | 30% | **Below Max** | **Increase generators** | Zwiększanie generatorów |
| **scenario_4_large_surplus_bess_full.json** | +315 kW | 90% (Full) | Max | Grid export | BESS pełny, eksport |
| **scenario_5_balanced.json** | 0 kW | 50% | Max | No action | Brak działania |
| **scenario_6_bess_charging_during_deficit_conflict.json** | -45.8 kW | 50% (Charging) | Max | Stop charging → BESS vs GRID | Konflikt ładowania |
| **scenario_7_bess_discharging_during_surplus_conflict.json** | +9.2 kW | 50% (Disch.) | Max | Stop disch. → BESS vs GRID | Konflikt rozładowania |
| **scenario_8_bess_minimum_cannot_discharge.json** | -125 kW | 10% (Min) | **Below Max** | **Increase generators** | BESS minimum, zwiększanie gen. |
| **scenario_9_contract_limits_exceeded.json** | +305 kW | 90% (Full) | Max | Grid export (limited) | Limity kontraktowe |

---

## 🔍 Szczegóły

### Deficyty (3 scenariusze)
- **scenario_1:** Mały deficyt (-15.8 kW), BESS może pomóc
- **scenario_3:** Duży deficyt (-125 kW), **zwiększ generatory**
- **scenario_6:** Deficit + BESS ładuje się (konflikt)
- **scenario_8:** Duży deficyt (-125 kW), BESS min, **zwiększ generatory**

### Nadwyżki (4 scenariusze)
- **scenario_2:** Mała nadwyżka (+8.7 kW), BESS może ładować
- **scenario_4:** Duża nadwyżka (+315 kW), BESS pełny
- **scenario_7:** Nadwyżka + BESS rozładowuje się (konflikt)
- **scenario_9:** Duża nadwyżka (+305 kW), limit kontraktowy

### Specjalne (2 scenariusze)
- **scenario_5:** Bilans zrównoważony (0 kW), brak działania
- **scenario_6, 7:** Konflikty operacyjne BESS

---

## ⚡ Kluczowe Różnice

### Generatory NA MAX (scenariusze 1, 2, 4, 5, 6, 7, 9)
- PV i Wind są na maksymalnej mocy
- **NIE MOŻNA** zwiększyć generatorów
- System musi użyć BESS/Grid/Loads

### Generatory BELOW MAX (scenariusze 3, 8)
- PV i Wind są **PONIŻEJ** maksymalnej mocy
- **MOŻNA** zwiększyć generatory
- System powinien najpierw zwiększyć generatory, potem BESS/Grid

---

## 🎯 Jak Używać

```bash
# Uruchom konkretny scenariusz
cp test_data/scenario_1_small_deficit_bess_mid.json apps/backend/initial_data.json
cp test_data/scenario_1_small_deficit_bess_mid.json apps/backend/contract_data.json
python main_algorithm.py

# Sprawdź logi
tail -f info.log
```

---

## 📊 Parametry Wspólne

- **BESS:** 100 kWh (10-90% usable range)
- **BESS Power:** 50 kW max charge/discharge
- **Contract:** 500 kWh sale, 200 kWh purchase
- **Tariffs:** 0.35 PLN/kWh buy, 0.25 PLN/kWh sell
- **Mode:** AUTO
- **Generatory:** Tylko PV i Wind (bez fuel_turbines/fuel_cells)

