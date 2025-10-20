# Drzewo Decyzyjne - System Zarządzania Energią

## 📊 **DEFICYT ENERGII** (Deficit)

### KROK 1: Maksymalizacja Produkcji (Zawsze pierwsze!)
```
handle_deficit_automatic(power_deficit)
    ↓
maximize_power_output(power_deficit)
    ↓
    ┌─────────────────────────────────────────────┐
    │  Zwiększ generatory (PV, Wind, Fuel)        │
    │  - Sortuj według priorytetu (rosnąco)       │
    │  - Dla każdego urządzenia:                  │
    │    • Jeśli adjustable → zwiększ do max      │
    │    • Jeśli non-adjustable → ustaw na max    │
    │  - Aktywuj nieaktywne urządzenia            │
    └─────────────────────────────────────────────┘
    ↓
    Oblicz: remaining_deficit = power_deficit - increased_power
```

### KROK 2: Zarządzanie Pozostałym Deficytem
```
manage_remaining_deficit(remaining_deficit)
    ↓
    ┌─────────────────────────────────────────────┐
    │  Sprawdź dostępność:                        │
    │  • bess_available = is_bess_available()     │
    │  • can_buy_energy = can_buy_energy()        │
    └─────────────────────────────────────────────┘
    ↓
    ┌─────────────────────────────────────────────────────────┐
    │  DECYZJA:                                               │
    │                                                         │
    │  ┌──────────────────────────────────────────────┐      │
    │  │ 1. BESS dostępny + GRID dostępny             │      │
    │  │    → handle_deficit_both_action()            │      │
    │  │    → Utility function (BESS vs GRID)         │      │
    │  │    → Wybierz BESS lub GRID                   │      │
    │  └──────────────────────────────────────────────┘      │
    │                        ↓                                │
    │  ┌──────────────────────────────────────────────┐      │
    │  │ 2. Tylko BESS dostępny                       │      │
    │  │    → _execute_discharge()                    │      │
    │  │    → Rozładowaj BESS                         │      │
    │  └──────────────────────────────────────────────┘      │
    │                        ↓                                │
    │  ┌──────────────────────────────────────────────┐      │
    │  │ 3. Tylko GRID dostępny                       │      │
    │  │    → _execute_buy()                          │      │
    │  │    → Kup energię z sieci                     │      │
    │  └──────────────────────────────────────────────┘      │
    │                        ↓                                │
    │  ┌──────────────────────────────────────────────┐      │
    │  │ 4. Żadna opcja niedostępna                   │      │
    │  │    → execute_action(LIMIT_CONSUMPTION)       │      │
    │  │    → Ogranicz zużycie (ostateczność)         │      │
    │  │    → Priority 3 → Priority 2                 │      │
    │  └──────────────────────────────────────────────┘      │
    └─────────────────────────────────────────────────────────┘
```

### Szczegóły: BESS vs GRID Decision
```
handle_deficit_both_action(power_deficit)
    ↓
    ┌─────────────────────────────────────────────┐
    │  KROK 1: Sprawdź fizyczne możliwości        │
    │  • BESS może rozładować?                    │
    │  • Grid może kupić?                         │
    └─────────────────────────────────────────────┘
    ↓
    ┌─────────────────────────────────────────────┐
    │  KROK 2: Utility Function                   │
    │  should_prioritize_discharging_or_buying()  │
    │                                             │
    │  Czynniki:                                  │
    │  • BESS charge level                        │
    │  • BESS min/max levels                      │
    │  • Grid tariff (buy/sell)                   │
    │  • Contract limits                          │
    │  • BESS health                              │
    │                                             │
    │  Wynik:                                     │
    │  • CHARGE (rozładowaj BESS)                 │
    │  • BUY (kup z grid)                         │
    └─────────────────────────────────────────────┘
    ↓
    Wykonaj wybraną akcję
```

---

## 📈 **NADWYŻKA ENERGII** (Surplus)

### KROK 1: Sprawdź Dostępność
```
manage_surplus_energy(power_surplus)
    ↓
    ┌─────────────────────────────────────────────┐
    │  Sprawdź dostępność:                        │
    │  • bess_available = check_bess_availability()│
    │  • export_possible = is_export_possible()   │
    └─────────────────────────────────────────────┘
    ↓
    ┌─────────────────────────────────────────────────────────┐
    │  DECYZJA:                                               │
    │                                                         │
    │  ┌──────────────────────────────────────────────┐      │
    │  │ 1. BESS dostępny + GRID dostępny             │      │
    │  │    → _decide_bess_vs_grid()                  │      │
    │  │    → Utility function (BESS vs GRID SELL)    │      │
    │  │    → Wybierz CHARGE lub SELL                 │      │
    │  └──────────────────────────────────────────────┘      │
    │                        ↓                                │
    │  ┌──────────────────────────────────────────────┐      │
    │  │ 2. Tylko BESS dostępny                       │      │
    │  │    → SurplusAction.CHARGE_BATTERY            │      │
    │  │    → Ładuj BESS                              │      │
    │  └──────────────────────────────────────────────┘      │
    │                        ↓                                │
    │  ┌──────────────────────────────────────────────┐      │
    │  │ 3. Tylko GRID dostępny                       │      │
    │  │    → SurplusAction.SELL_ENERGY               │      │
    │  │    → Sprzedaj do sieci                       │      │
    │  └──────────────────────────────────────────────┘      │
    │                        ↓                                │
    │  ┌──────────────────────────────────────────────┐      │
    │  │ 4. Żadna opcja niedostępna                   │      │
    │  │    → SurplusAction.LIMIT_GENERATION          │      │
    │  │    → Ogranicz generację (ostateczność)       │      │
    │  └──────────────────────────────────────────────┘      │
    └─────────────────────────────────────────────────────────┘
```

### Szczegóły: BESS vs GRID SELL Decision
```
_decide_bess_vs_grid(surplus)
    ↓
    ┌─────────────────────────────────────────────┐
    │  Utility Function                           │
    │  should_prioritize_charging_or_selling()    │
    │                                             │
    │  Czynniki:                                  │
    │  • BESS charge level                        │
    │  • BESS free capacity                       │
    │  • Grid tariff (sell price)                 │
    │  • Contract sale limit                      │
    │  • BESS health                              │
    │                                             │
    │  Wynik:                                     │
    │  • CHARGE (ładuj BESS)                      │
    │  • SELL (sprzedaj do grid)                  │
    └─────────────────────────────────────────────┘
```

---

## 🔄 **GŁÓWNY ALGORYTM**

```
check_energy_conditions()
    ↓
    ┌─────────────────────────────────────────────┐
    │  KROK 1: Oblicz początkowy bilans           │
    │  initial_balance = calculate_energy_balance()│
    └─────────────────────────────────────────────┘
    ↓
    ┌─────────────────────────────────────────────┐
    │  KROK 2: Sprawdź czy bilans OK              │
    │  if initial_balance.is_balanced():          │
    │      return "balanced"                      │
    └─────────────────────────────────────────────┘
    ↓
    ┌─────────────────────────────────────────────┐
    │  KROK 3: Neutralizuj konflikty              │
    │  balance = neutralize_conflicting_operations()│
    │                                             │
    │  Konflikty:                                 │
    │  • BESS ładuje się podczas deficytu         │
    │  • BESS rozładowuje się podczas nadwyżki    │
    └─────────────────────────────────────────────┘
    ↓
    ┌─────────────────────────────────────────────┐
    │  KROK 4: Sprawdź czy po neutralizacji OK    │
    │  if balance.is_balanced():                  │
    │      return "balanced"                      │
    └─────────────────────────────────────────────┘
    ↓
    ┌─────────────────────────────────────────────┐
    │  KROK 5: Zarządzaj deficytem/nadwyżką       │
    │                                             │
    │  if balance.has_deficit:                    │
    │      manage_deficit(balance.deficit)        │
    │         ↓                                   │
    │      1. maximize_power_output()             │
    │      2. manage_remaining_deficit()          │
    │                                             │
    │  elif balance.has_surplus:                  │
    │      manage_surplus(balance.surplus)        │
    │         ↓                                   │
    │      1. BESS vs GRID decision               │
    │      2. Execute chosen action               │
    └─────────────────────────────────────────────┘
    ↓
    ┌─────────────────────────────────────────────┐
    │  KROK 6: Oblicz końcowy bilans              │
    │  final_balance = calculate_energy_balance() │
    └─────────────────────────────────────────────┘
    ↓
    ┌─────────────────────────────────────────────┐
    │  KROK 7: Loguj podsumowanie                 │
    │  _log_simple_summary(...)                   │
    └─────────────────────────────────────────────┘
```

---

## 🎯 **PRIORYTETY AKCJI**

### Dla Deficytu:
1. **Zwiększ generatory** (PV, Wind, Fuel) - zawsze pierwsze!
2. **BESS discharge vs GRID import** - decyzja przez utility function
3. **Ogranicz zużycie** (priority 3 → 2) - ostateczność

### Dla Nadwyżki:
1. **BESS charge vs GRID SELL** - decyzja przez utility function
2. **Ogranicz generację** - ostateczność

---

## ⚙️ **UTILITY FUNCTIONS**

### BESS vs GRID (Deficit):
```python
should_prioritize_discharging_or_buying(
    charge_level, min_charge_level, max_charge_level,
    tariff_buy, tariff_sell,
    bought_power, purchase_limit,
    config, info_logger, error_logger
)
```

### BESS vs GRID SELL (Surplus):
```python
should_prioritize_charging_or_selling(
    charge_level, min_charge_level, max_charge_level,
    tariff_sell, tariff_buy,
    sold_power, sale_limit,
    config, info_logger, error_logger
)
```

---

## 🔒 **BEZPIECZEŃSTWO**

### BESS Safety Checks:
- **Minimum charge level** (10%) - nie rozładowuj poniżej
- **Maximum charge level** (90%) - nie ładuj powyżej
- **Max discharge power** (50 kW)
- **Max charge power** (50 kW)
- **Health check** - czy BESS może operować

### Grid Safety Checks:
- **Contract limits** - nie przekrocz limitów
- **Export possibility** - czy można eksportować
- **Import possibility** - czy można importować

### Generator Safety Checks:
- **Max output** - nie przekrocz maksymalnej mocy
- **Min output** - nie zejdź poniżej minimum
- **Switch status** - sprawdź czy urządzenie jest włączone

---

## 📝 **NOTATKI**

1. **Deficit zawsze zaczyna od zwiększania generatorów** - to jest priorytet #1
2. **Surplus nie zwiększa generatorów** - tylko BESS/Grid/Limit
3. **Konflikty są neutralizowane przed decyzjami** - BESS nie może ładować podczas deficytu
4. **Utility functions** używają wielu czynników do podjęcia decyzji
5. **Iteracje** - system próbuje pokryć cały deficit/surplus w pętli

