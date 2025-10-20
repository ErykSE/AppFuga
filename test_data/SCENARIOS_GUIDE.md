# Przewodnik po Scenariuszach Testowych

Wszystkie scenariusze używają **tylko PV i Wind Turbines** (bez fuel_turbines i fuel_cells).

---

## 📁 **scenario_1_small_deficit_bess_mid.json**

### Stan początkowy:
- **Generacja:** 303.71 kW (PV: 136.71 kW, Wind: 167 kW)
- **Konsumpcja:** 295 kW (Critical: 155 kW, Adjustable: 140 kW)
- **Bilans:** **-15.8 kW (DEFICIT)**
- **BESS:** 50 kWh/100 kWh (50%) - może rozładować do 50 kW

### Co powinien zrobić system:
1. **NIE MOŻE** zwiększyć generatorów (PV i Wind są NA MAX)
2. **Decyzja:** BESS discharge vs GRID import
3. **Opcjonalnie:** Reduce adjustable loads (priority 3)

### Oczekiwany wynik:
- System powinien podjąć decyzję BESS vs GRID na podstawie utility function
- Jeśli BESS: rozładować ~16 kW
- Jeśli GRID: importować ~16 kW

---

## 📁 **scenario_2_small_surplus_bess_mid.json**

### Stan początkowy:
- **Generacja:** 303.71 kW (PV: 136.71 kW, Wind: 167 kW)
- **Konsumpcja:** 270 kW (Critical: 155 kW, Adjustable: 115 kW)
- **Bilans:** **+8.7 kW (SURPLUS)**
- **BESS:** 50 kWh/100 kWh (50%) - może ładować do 40 kWh

### Co powinien zrobić system:
1. **NIE MOŻE** zwiększyć generatorów (PV i Wind są NA MAX)
2. **Decyzja:** BESS charge vs GRID SELL

### Oczekiwany wynik:
- System powinien podjąć decyzję BESS vs GRID SELL na podstawie utility function
- Jeśli BESS: ładować ~9 kW
- Jeśli GRID: eksportować ~9 kW

---

## 📁 **scenario_3_large_deficit_grid_required.json**

### Stan początkowy:
- **Generacja:** 80 kW (PV: 45 kW, Wind: 35 kW)
- **Konsumpcja:** 425 kW (Critical: 155 kW, Adjustable: 270 kW)
- **Bilans:** **-125 kW (DEFICIT)**
- **BESS:** 30 kWh/100 kWh (30%) - może rozładować do 50 kW

### Co powinien zrobić system:
1. **MOŻE** zwiększyć generatory:
   - PV Panel 1: 20 → 100 kW (+80 kW)
   - PV Panel 2: 25 → 100 kW (+75 kW)
   - Wind Turbine 1: 10 → 90 kW (+80 kW)
   - Wind Turbine 2: 15 → 90 kW (+75 kW)
   - **Razem:** +310 kW możliwości
2. **Strategia:** Zwiększyć generatory o 125 kW (wystarczy!)
3. **Alternatywnie:** BESS discharge (50 kW) + Grid import (75 kW) + reduce loads

### Oczekiwany wynik:
- **Najlepsze rozwiązanie:** Zwiększyć generatory o 125 kW
- **Alternatywa:** BESS discharge + Grid import + reduce loads

---

## 📁 **scenario_4_large_surplus_bess_full.json**

### Stan początkowy:
- **Generacja:** 380 kW (PV: 200 kW, Wind: 180 kW)
- **Konsumpcja:** 225 kW (Critical: 155 kW, Adjustable: 70 kW)
- **Bilans:** **+315 kW (SURPLUS)**
- **BESS:** 90 kWh/100 kWh (90%) - **PEŁNY, NIE MOŻE ŁADOWAĆ**

### Co powinien zrobić system:
1. **NIE MOŻE** zwiększyć generatorów (PV i Wind są NA MAX)
2. **NIE MOŻE** ładować BESS (jest pełny)
3. **Jedyna opcja:** Grid export

### Oczekiwany wynik:
- System powinien eksportować całą nadwyżkę (315 kW) do sieci
- Grid export: 315 kW

---

## 📁 **scenario_5_balanced.json**

### Stan początkowy:
- **Generacja:** 303.71 kW (PV: 136.71 kW, Wind: 167 kW)
- **Konsumpcja:** 303.71 kW (Critical: 155 kW, Adjustable: 148.71 kW)
- **Bilans:** **0 kW (BALANCED)**
- **BESS:** 50 kWh/100 kWh (50%)

### Co powinien zrobić system:
1. **Brak działania** - system jest zbalansowany

### Oczekiwany wynik:
- System nie powinien podejmować żadnych działań
- Status: "balanced"

---

## 📁 **scenario_6_bess_charging_during_deficit_conflict.json**

### Stan początkowy:
- **Generacja:** 303.71 kW (PV: 136.71 kW, Wind: 167 kW)
- **Konsumpcja:** 295 kW (Critical: 155 kW, Adjustable: 140 kW)
- **BESS:** 50 kWh/100 kWh (50%) - **ŁADUJE SIĘ 30 kW**
- **Bilans:** **-45.8 kW (DEFICIT)** - BESS ładuje się podczas deficytu!

### Co powinien zrobić system:
1. **KONFLIKT:** BESS ładuje się podczas deficytu
2. **KROK 1:** Zatrzymać ładowanie BESS (neutralizacja konfliktu)
3. **KROK 2:** Nowy bilans: -15.8 kW (bez ładowania)
4. **Decyzja:** BESS discharge vs GRID import

### Oczekiwany wynik:
- System powinien **zatrzymać ładowanie BESS**
- Następnie podjąć decyzję BESS discharge vs GRID import dla -15.8 kW

---

## 📁 **scenario_7_bess_discharging_during_surplus_conflict.json**

### Stan początkowy:
- **Generacja:** 303.71 kW (PV: 136.71 kW, Wind: 167 kW)
- **Konsumpcja:** 270 kW (Critical: 155 kW, Adjustable: 115 kW)
- **BESS:** 50 kWh/100 kWh (50%) - **ROZŁADOWUJE SIĘ 25 kW**
- **Bilans:** **+9.2 kW (SURPLUS)** - BESS rozładowuje się podczas nadwyżki!

### Co powinien zrobić system:
1. **KONFLIKT:** BESS rozładowuje się podczas nadwyżki
2. **KROK 1:** Zatrzymać rozładowanie BESS (neutralizacja konfliktu)
3. **KROK 2:** Nowy bilans: +34.2 kW (bez rozładowania)
4. **Decyzja:** BESS charge vs GRID SELL

### Oczekiwany wynik:
- System powinien **zatrzymać rozładowanie BESS**
- Następnie podjąć decyzję BESS charge vs GRID SELL dla +34.2 kW

---

## 📁 **scenario_8_bess_minimum_cannot_discharge.json**

### Stan początkowy:
- **Generacja:** 80 kW (PV: 45 kW, Wind: 35 kW)
- **Konsumpcja:** 425 kW (Critical: 155 kW, Adjustable: 270 kW)
- **Bilans:** **-125 kW (DEFICIT)**
- **BESS:** 10 kWh/100 kWh (10%) - **MINIMUM, NIE MOŻE ROZŁADOWAĆ**

### Co powinien zrobić system:
1. **MOŻE** zwiększyć generatory:
   - PV Panel 1: 20 → 100 kW (+80 kW)
   - PV Panel 2: 25 → 100 kW (+75 kW)
   - Wind Turbine 1: 10 → 90 kW (+80 kW)
   - Wind Turbine 2: 15 → 90 kW (+75 kW)
   - **Razem:** +310 kW możliwości
2. **Strategia:** Zwiększyć generatory o 125 kW (wystarczy!)
3. **Alternatywnie:** Grid import (125 kW) + reduce loads

### Oczekiwany wynik:
- **Najlepsze rozwiązanie:** Zwiększyć generatory o 125 kW
- **Alternatywa:** Grid import + reduce loads

---

## 📁 **scenario_9_contract_limits_exceeded.json**

### Stan początkowy:
- **Generacja:** 380 kW (PV: 200 kW, Wind: 180 kW)
- **Konsumpcja:** 225 kW (Critical: 155 kW, Adjustable: 70 kW)
- **Bilans:** **+305 kW (SURPLUS)**
- **BESS:** 90 kWh/100 kWh (90%) - **PEŁNY**
- **Contract:** 480/500 kWh sprzedane (tylko 20 kWh pozostało)

### Co powinien zrobić system:
1. **NIE MOŻE** ładować BESS (jest pełny)
2. **Grid export ograniczony:** tylko 20 kWh (limit kontraktowy)
3. **Problem:** 305 kW nadwyżki, ale tylko 20 kWh można sprzedać

### Oczekiwany wynik:
- System powinien eksportować 20 kWh do sieci (limit kontraktowy)
- Pozostałe 285 kW - **curtail generation** (ograniczyć produkcję)

---

## 📊 Podsumowanie Pokrycia Testowego

| Scenariusz | Deficit | Surplus | BESS State | Konflikt | Generatory | Grid | Loads | Contract |
|------------|---------|---------|------------|----------|------------|------|-------|----------|
| 1          | Mały    | -       | Mid        | -        | Max        | ✓    | ✓     | -       |
| 2          | -       | Mały    | Mid        | -        | Max        | ✓    | -     | -       |
| 3          | Duży    | -       | Mid        | -        | **Below**  | ✓    | ✓     | -       |
| 4          | -       | Duży    | Full       | -        | Max        | ✓    | -     | -       |
| 5          | -       | -       | Mid        | -        | Max        | -    | -     | -       |
| 6          | Mały    | -       | Mid        | Charging | Max        | ✓    | ✓     | -       |
| 7          | -       | Mały    | Mid        | Disch.   | Max        | ✓    | -     | -       |
| 8          | Duży    | -       | Min        | -        | **Below**  | ✓    | ✓     | -       |
| 9          | -       | Duży    | Full       | -        | Max        | ✓    | -     | Limit   |

**Legenda:**
- **Generatory Below Max:** Można zwiększyć PV/Wind
- **Generatory Max:** PV/Wind są na maksimum, nie można zwiększyć

---

## 🎯 Kluczowe Testy

1. **Scenariusz 3 i 8:** Testują zwiększanie generatorów (PV/Wind below max)
2. **Scenariusz 6 i 7:** Testują wykrywanie i neutralizację konfliktów
3. **Scenariusz 9:** Testuje obsługę limitów kontraktowych
4. **Scenariusz 5:** Testuje brak działania przy zbalansowanym systemie

