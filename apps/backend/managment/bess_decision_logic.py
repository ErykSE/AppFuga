"""
Modułowa logika decyzyjna dla BESS - Wersja V1.
Implementacja funkcji użyteczności z wagami ekonomicznymi, storage i ryzykiem.

Wersja V1: Rule-based + tryby użytkownika (bias)
Plan rozwoju:
  V2: Dynamiczne wagi i adaptacja
  V3: Predykcyjna analiza
  V4: AI/RL (uczenie maszynowe)

Autor: System zarządzania energią
Data: 2025-01-10
"""

from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional
from enum import Enum

# Małe epsilon dla bezpiecznych obliczeń
EPSILON = 1e-6


class DecisionMode(Enum):
    """
    Tryby zarządzania energią - uniwersalne dla surplus i deficit.
    
    Filozofia: Operator wybiera PRIORYTET (BESS vs GRID), nie konkretną akcję.
    
    === TRYBY ===
    
    AUTO (domyślny):
    - Algorytm decyduje na podstawie utility function
    - Bierze pod uwagę: ekonomię, stan BESS, ryzyko (limity)
    - Brak biasu - czysta optymalizacja
    
    BESS_PRIORITY:
    - Preferuj wykorzystanie baterii w każdej sytuacji
    - SURPLUS: Priorytet ładowania BESS (bias +0.2 do U_charge)
    - DEFICIT: Priorytet rozładowania BESS (bias +0.2 do U_discharge)
    - Używaj grid tylko gdy BESS nie wystarcza
    - Przykład: Operator chce maksymalnie wykorzystać BESS, minimalizować handel
    
    GRID_PRIORITY:
    - Preferuj handel z siecią w każdej sytuacji
    - SURPLUS: Priorytet sprzedaży do grid (bias +0.2 do U_sell)
    - DEFICIT: Priorytet zakupu z grid (bias +0.2 do U_buy)
    - Używaj BESS tylko gdy grid nie wystarcza lub jest nieopłacalny
    - Przykład: Operator chce oszczędzać BESS (wydłużyć żywotność), aktywnie handlować
    
    === MAPOWANIE DLA KODU ===
    
    W funkcji should_prioritize_charging_or_selling() (SURPLUS):
        AUTO           → bias = 0
        BESS_PRIORITY  → U_charge += 0.2  (preferuj ładowanie)
        GRID_PRIORITY  → U_sell += 0.2    (preferuj sprzedaż)
    
    W funkcji should_prioritize_discharging_or_buying() (DEFICIT):
        AUTO           → bias = 0
        BESS_PRIORITY  → U_discharge += 0.2  (preferuj rozładowanie)
        GRID_PRIORITY  → U_buy += 0.2        (preferuj zakup)
    
    === API CONTRACT_DATA ===
    
    {
        "decision_mode": "AUTO",  // lub "BESS_PRIORITY" lub "GRID_PRIORITY"
        // ... reszta pól
    }
    """
    
    AUTO = "AUTO"
    BESS_PRIORITY = "BESS_PRIORITY"
    GRID_PRIORITY = "GRID_PRIORITY"



@dataclass
class DecisionConfig:
    """Konfiguracja parametrów decyzyjnych."""
    
    # === WAGI FUNKCJI UŻYTECZNOŚCI ===
    # Suma = 1.0, określają jak mocno każdy czynnik wpływa na decyzję
    w1_economics: float = 0.6      # Ekonomia (ceny energii)
    w2_storage: float = 0.3        # Stan BESS (wolna przestrzeń)
    w3_risk: float = 0.1           # Ryzyko (limity sprzedaży)
    
    # === TRYB UŻYTKOWNIKA (z API) ===
    mode: DecisionMode = DecisionMode.AUTO  # ← JEDYNY z API
    
    # === PARAMETRY TECHNICZNE ===
    bias_value: float = 0.2                      # Siła biasu dla trybów preferencyjnych
    sell_buy_ratio_threshold: float = 0.75       # Próg opłacalności sprzedaży
    critical_free_space: float = 10.0            # % - krytyczny poziom wolnej przestrzeni
    bess_roundtrip_efficiency: float = 0.90      # Sprawność cyklu BESS (na przyszłość)
    
    def validate(self):
        """Waliduje konfigurację."""
        # Sprawdź sumy wag
        total_weight = self.w1_economics + self.w2_storage + self.w3_risk
        if abs(total_weight - 1.0) > 0.01:
            raise ValueError(f"Suma wag musi wynosić 1.0, otrzymano: {total_weight}")
        
        # Sprawdź zakresy
        if not (0 <= self.sell_buy_ratio_threshold <= 2.0):
            raise ValueError("sell_buy_ratio_threshold powinien być w zakresie 0-2")
        
        if not (0 <= self.critical_free_space <= 100):
            raise ValueError("critical_free_space powinien być w zakresie 0-100%")


@dataclass
class DecisionResult:
    """Wynik decyzji."""
    
    decision: bool  # True = CHARGE, False = SELL
    reason: str
    confidence: float  # 0-1, jak bardzo preferujemy tę decyzję
    utility_charge: float
    utility_sell: float
    score_details: Dict[str, Any]


# ============================================================================
# FUNKCJE OCENY KOMPONENTÓW
# ============================================================================

def evaluate_economics(
    tariff_sell: float,
    tariff_buy: float,
    info_logger=None
) -> Dict[str, float]:
    """
    Ocenia składnik ekonomiczny E(a) dla ładowania i sprzedaży.
    
    Zwraca score w zakresie [-1, 1]:
    - E_sell > 0: Sprzedaż korzystna (cena sprzedaży bliska cenie zakupu)
    - E_sell < 0: Sprzedaż niekorzystna (cena sprzedaży << cena zakupu)
    - E_charge = -E_sell
    
    Args:
        tariff_sell: Aktualna cena sprzedaży ($/kWh)
        tariff_buy: Aktualna cena zakupu ($/kWh)
        info_logger: Logger do informacji
        
    Returns:
        Dict z E_charge, E_sell, ratio
    """
    buy = max(tariff_buy, EPSILON)
    sell = tariff_sell
    
    # Stosunek cen: sell/buy
    ratio = sell / buy
    
    # Normalizacja do [-1, 1]
    # ratio = 1.0 → E_sell = 0 (neutralne)
    # ratio > 1.0 → E_sell > 0 (korzystne)
    # ratio < 1.0 → E_sell < 0 (niekorzystne)
    
    # Przekształcenie: ratio ∈ [0, 2] → E_sell ∈ [-1, 1]
    # ratio = 0.5 → E_sell = -1.0 (bardzo niekorzystne)
    # ratio = 1.0 → E_sell = 0.0 (neutralne)
    # ratio = 1.5 → E_sell = 0.5 (korzystne)
    # ratio = 2.0 → E_sell = 1.0 (bardzo korzystne)
    
    E_sell = max(-1.0, min(1.0, 2 * (ratio - 0.75)))
    E_charge = -E_sell
    
    if info_logger:
        info_logger.debug(
            f"Economics: sell={sell:.3f}, buy={buy:.3f}, "
            f"ratio={ratio:.3f}, E_sell={E_sell:.3f}, E_charge={E_charge:.3f}"
        )
    
    return {
        "E_charge": E_charge,
        "E_sell": E_sell,
        "ratio": ratio
    }


def evaluate_bess_state(
    charge_level: float,
    min_charge_level: float,
    max_charge_level: float,
    info_logger=None
) -> Dict[str, float]:
    """
    Ocenia składnik stanu BESS S(a).
    
    Zwraca score w zakresie [-1, 1]:
    - S_charge > 0: Dużo wolnego miejsca (korzystne ładowanie)
    - S_charge < 0: Mało wolnego miejsca (niekorzystne ładowanie)
    - S_sell = -S_charge
    
    Args:
        charge_level: Aktualny poziom naładowania (kWh)
        min_charge_level: Minimalny poziom (kWh)
        max_charge_level: Maksymalny poziom (kWh)
        info_logger: Logger
        
    Returns:
        Dict z S_charge, S_sell, free_space_percent, remaining_capacity
    """
    usable_capacity = max(max_charge_level - min_charge_level, EPSILON)
    remaining_capacity = max(max_charge_level - charge_level, 0.0)
    free_space_percent = (remaining_capacity / usable_capacity) * 100.0
    
    # Normalizacja do [-1, 1]
    # free_space = 0% → S_charge = -1.0 (brak miejsca)
    # free_space = 50% → S_charge = 0.0 (neutralne)
    # free_space = 100% → S_charge = 1.0 (pełno miejsca)
    
    S_charge = (free_space_percent / 50.0) - 1.0
    S_charge = max(-1.0, min(1.0, S_charge))
    S_sell = -S_charge
    
    if info_logger:
        info_logger.debug(
            f"BESS State: level={charge_level:.2f}, "
            f"remaining={remaining_capacity:.2f} kWh ({free_space_percent:.1f}%), "
            f"S_charge={S_charge:.3f}, S_sell={S_sell:.3f}"
        )
    
    return {
        "S_charge": S_charge,
        "S_sell": S_sell,
        "free_space_percent": free_space_percent,
        "remaining_capacity": remaining_capacity,
        "usable_capacity": usable_capacity
    }


def evaluate_risk(
    sold_power: float,
    sale_limit: Optional[float],
    info_logger=None
) -> Dict[str, float]:
    """
    Ocenia składnik ryzyka R(a).
    
    Zwraca score w zakresie [-1, 1]:
    - R_sell > 0: Małe ryzyko (daleko od limitu)
    - R_sell < 0: Duże ryzyko (blisko limitu)
    - R_charge ≈ 0 (neutralne)
    
    Args:
        sold_power: Już sprzedana moc w okresie rozliczeniowym (kWh)
        sale_limit: Limit sprzedaży (kWh) lub None
        info_logger: Logger
        
    Returns:
        Dict z R_charge, R_sell, usage_percent
    """
    # Ryzyko ładowania - neutralne (degradacja baterii jest stała)
    R_charge = 0.0
    
    # Ryzyko sprzedaży - zależy od wykorzystania limitu
    if sale_limit is None or sale_limit <= 0:
        # Brak limitu → brak ryzyka
        R_sell = 1.0
        usage_percent = 0.0
    else:
        usage = min(1.0, sold_power / (sale_limit + EPSILON))
        usage_percent = usage * 100.0
        
        # usage = 0% → R_sell = +1.0 (bezpiecznie)
        # usage = 50% → R_sell = 0.0 (neutralne)
        # usage = 100% → R_sell = -1.0 (niebezpiecznie)
        R_sell = 1.0 - 2.0 * usage
        R_sell = max(-1.0, min(1.0, R_sell))
    
    if info_logger:
        info_logger.debug(
            f"Risk: sold={sold_power:.2f}, limit={sale_limit}, "
            f"usage={usage_percent:.1f}%, R_sell={R_sell:.3f}"
        )
    
    return {
        "R_charge": R_charge,
        "R_sell": R_sell,
        "usage_percent": usage_percent
    }


def compute_utility(
    E_charge: float,
    E_sell: float,
    S_charge: float,
    S_sell: float,
    R_charge: float,
    R_sell: float,
    config: DecisionConfig,
    info_logger=None
) -> Dict[str, float]:
    """
    Oblicza funkcje użyteczności dla obu akcji.
    
    U_charge = w1*E_charge + w2*S_charge + w3*R_charge
    U_sell = w1*E_sell + w2*S_sell + w3*R_sell
    
    Args:
        E_charge, E_sell: Składniki ekonomiczne
        S_charge, S_sell: Składniki stanu BESS
        R_charge, R_sell: Składniki ryzyka
        config: Konfiguracja wag
        info_logger: Logger
        
    Returns:
        Dict z U_charge, U_sell
    """
    U_charge = (
        config.w1_economics * E_charge +
        config.w2_storage * S_charge +
        config.w3_risk * R_charge
    )
    
    U_sell = (
        config.w1_economics * E_sell +
        config.w2_storage * S_sell +
        config.w3_risk * R_sell
    )
    
    if info_logger:
        info_logger.debug(
            f"Utility: U_charge={U_charge:.4f} "
            f"(E={config.w1_economics * E_charge:.3f}, "
            f"S={config.w2_storage * S_charge:.3f}, "
            f"R={config.w3_risk * R_charge:.3f})"
        )
        info_logger.debug(
            f"Utility: U_sell={U_sell:.4f} "
            f"(E={config.w1_economics * E_sell:.3f}, "
            f"S={config.w2_storage * S_sell:.3f}, "
            f"R={config.w3_risk * R_sell:.3f})"
        )
    
    return {
        "U_charge": U_charge,
        "U_sell": U_sell
    }


def apply_user_mode_bias(U_charge, U_sell, config, info_logger=None):
    bias_applied = 0.0
    
    if config.mode == DecisionMode.BESS_PRIORITY:
        U_charge += config.bias_value
        bias_applied = config.bias_value
        if info_logger:
            info_logger.info(f"Applied BESS_PRIORITY: +{config.bias_value:.2f} to U_charge")
    
    elif config.mode == DecisionMode.GRID_PRIORITY:
        U_sell += config.bias_value
        bias_applied = config.bias_value
        if info_logger:
            info_logger.info(f"Applied GRID_PRIORITY: +{config.bias_value:.2f} to U_sell")
    
    return {
        "U_charge_final": U_charge,
        "U_sell_final": U_sell,
        "bias_applied": bias_applied
    }


# ============================================================================
# GŁÓWNA FUNKCJA DECYZYJNA
# ============================================================================

def should_prioritize_charging_or_selling(
    # Dane BESS (z API)
    charge_level: float,
    min_charge_level: float,
    max_charge_level: float,
    
    # Dane sieci (z API)
    tariff_sell: float,
    tariff_buy: float,
    sold_power: float,
    sale_limit: Optional[float],
    
    # Konfiguracja
    config: DecisionConfig,
    
    # Logger
    info_logger=None,
    error_logger=None
) -> DecisionResult:
    """
    Główna funkcja decyzyjna - TYLKO porównanie opcji i wybór lepszej.
    
    ZAŁOŻENIE: Wszystkie ograniczenia fizyczne (BESS włączony, możliwość sprzedaży,
    limity mocy) zostały sprawdzone WCZEŚNIEJ. Tutaj tylko decydujemy CO JEST LEPSZE.
    
    Args:
        charge_level: Aktualny poziom naładowania BESS (kWh)
        min_charge_level: Minimalny bezpieczny poziom (kWh)
        max_charge_level: Maksymalny bezpieczny poziom (kWh)
        tariff_sell: Aktualna cena sprzedaży ($/kWh)
        tariff_buy: Aktualna cena zakupu ($/kWh)
        sold_power: Już sprzedana energia w okresie rozliczeniowym (kWh)
        sale_limit: Limit sprzedaży (kWh) lub None
        config: Konfiguracja DecisionConfig
        info_logger: Logger do informacji
        error_logger: Logger do błędów
        
    Returns:
        DecisionResult z decyzją, uzasadnieniem i szczegółami
    """
    
    if info_logger:
        info_logger.info("=" * 70)
        info_logger.info("DECISION ANALYSIS - should_prioritize_charging_or_selling()")
        info_logger.info(f"  Mode: {config.mode.value}")
        info_logger.info("")
    
    # Waliduj konfigurację
    try:
        config.validate()
    except ValueError as e:
        if error_logger:
            error_logger.error(f"Invalid configuration: {e}")
        raise
    
    # === KROK 1: Oblicz komponenty ===
    
    econ = evaluate_economics(tariff_sell, tariff_buy, info_logger)
    bess = evaluate_bess_state(charge_level, min_charge_level, max_charge_level, info_logger)
    risk = evaluate_risk(sold_power, sale_limit, info_logger)
    
    # === KROK 2: Oblicz utility ===
    
    utility = compute_utility(
        econ["E_charge"], econ["E_sell"],
        bess["S_charge"], bess["S_sell"],
        risk["R_charge"], risk["R_sell"],
        config, info_logger
    )
    
    U_charge_raw = utility["U_charge"]
    U_sell_raw = utility["U_sell"]
    
    # === KROK 3: Aplikuj bias użytkownika ===
    
    biased = apply_user_mode_bias(U_charge_raw, U_sell_raw, config, info_logger)
    
    U_charge_final = biased["U_charge_final"]
    U_sell_final = biased["U_sell_final"]
    
    # === KROK 4: Decyzja ===
    
    decision_charge = U_charge_final > U_sell_final
    
    # Oblicz confidence (jak mocna jest przewaga)
    utility_diff = abs(U_charge_final - U_sell_final)
    confidence = min(1.0, utility_diff / 2.0)  # Różnica 2.0 = 100% confidence
    
    # === KROK 5: Uzasadnienie ===
    
    reason_parts = []
    
    # Ekonomia
    if econ["ratio"] >= config.sell_buy_ratio_threshold:
        reason_parts.append(f"good_sell_price(ratio={econ['ratio']:.2f})")
    else:
        reason_parts.append(f"poor_sell_price(ratio={econ['ratio']:.2f})")
    
    # Stan BESS
    free_percent = bess["free_space_percent"]
    if free_percent < config.critical_free_space:
        reason_parts.append(f"critical_free_space({free_percent:.1f}%)")
    elif free_percent > 70:
        reason_parts.append(f"high_free_space({free_percent:.1f}%)")
    else:
        reason_parts.append(f"moderate_free_space({free_percent:.1f}%)")
    
    # Ryzyko
    if risk["usage_percent"] > 80:
        reason_parts.append(f"high_limit_usage({risk['usage_percent']:.0f}%)")
    
    # Tryb
    if config.mode != DecisionMode.AUTO:
        reason_parts.append(f"mode={config.mode.value}")
    
    # Utility
    reason_parts.append(f"U_charge={U_charge_final:.3f}")
    reason_parts.append(f"U_sell={U_sell_final:.3f}")
    
    decision_text = "CHARGE" if decision_charge else "SELL"
    reason = f"{decision_text}: " + ", ".join(reason_parts)
    
    # === KROK 6: Szczegóły do logów ===
    
    score_details = {
        # Komponenty
        "E_charge": econ["E_charge"],
        "E_sell": econ["E_sell"],
        "S_charge": bess["S_charge"],
        "S_sell": bess["S_sell"],
        "R_charge": risk["R_charge"],
        "R_sell": risk["R_sell"],
        
        # Utility
        "U_charge_raw": U_charge_raw,
        "U_sell_raw": U_sell_raw,
        "U_charge_final": U_charge_final,
        "U_sell_final": U_sell_final,
        
        # Dane wejściowe
        "ratio": econ["ratio"],
        "free_space_percent": free_percent,
        "remaining_capacity": bess["remaining_capacity"],
        "usage_percent": risk["usage_percent"],
        
        # Konfiguracja
        "weights": {
            "w1_economics": config.w1_economics,
            "w2_storage": config.w2_storage,
            "w3_risk": config.w3_risk
        },
        "mode": config.mode.value,
        "bias_applied": biased["bias_applied"]
    }
    
    # === KROK 7: Logowanie ===
    
    if info_logger:
        info_logger.info("-" * 70)
        info_logger.info(f"  Decision: {'CHARGE' if decision_charge else 'SELL'}")
        info_logger.info(f"  Confidence: {confidence*100:.1f}%")
        info_logger.info(f"  Reason: {reason}")
        info_logger.info("=" * 70)
    
    return DecisionResult(
        decision=decision_charge,
        reason=reason,
        confidence=confidence,
        utility_charge=U_charge_final,
        utility_sell=U_sell_final,
        score_details=score_details
    )

"""
POPRAWIONA FUNKCJA DECYZYJNA DLA DEFICYTU
Usuwa reguły bezpieczeństwa - tylko porównuje utility
"""

def should_prioritize_discharging_or_buying(
    charge_level: float,
    min_charge_level: float,
    max_charge_level: float,
    tariff_buy: float,
    tariff_sell: float,
    bought_power: float,
    purchase_limit: Optional[float],
    config: DecisionConfig,
    info_logger=None,
    error_logger=None
) -> DecisionResult:
    """
    Decyduje czy lepiej rozładować BESS czy kupić energię z grid przy deficycie.
    
    ZAŁOŻENIE: Obie opcje są FIZYCZNIE MOŻLIWE (sprawdzone wcześniej)
    - BESS może rozładować (BESSCapabilityChecker.check_discharge_capability)
    - Można kupić z grid (OSD.can_buy_energy + limit check)
    
    USUNIĘTE: Reguły bezpieczeństwa (bess_low_threshold)
    TYLKO: Porównanie utility DISCHARGE vs BUY
    
    Args:
        charge_level: Aktualny poziom naładowania BESS (kWh)
        min_charge_level: Minimalny bezpieczny poziom (kWh)
        max_charge_level: Maksymalny poziom (kWh)
        tariff_buy: Aktualna cena zakupu energii ($/kWh)
        tariff_sell: Cena sprzedaży (dla porównania wartości) ($/kWh)
        bought_power: Już kupiona energia w okresie (kWh)
        purchase_limit: Limit zakupu (kWh) lub None
        config: Konfiguracja DecisionConfig
        info_logger: Logger
        error_logger: Logger
        
    Returns:
        DecisionResult:
            decision=True → DISCHARGE (rozładuj BESS)
            decision=False → BUY (kup z grid)
    """
    
    if info_logger:
        info_logger.info("=" * 70)
        info_logger.info("DEFICIT DECISION ANALYSIS - should_prioritize_discharging_or_buying()")
        info_logger.info(f"  Mode: {config.mode.value}")
        info_logger.info("  ASSUMPTION: Both DISCHARGE and BUY are physically possible")
    
    try:
        config.validate()
    except ValueError as e:
        if error_logger:
            error_logger.error(f"Invalid configuration: {e}")
        raise
    
    # === KROK 1: Oblicz stan BESS ===
    usable_capacity = max(max_charge_level - min_charge_level, EPSILON)
    charge_percent = (charge_level - min_charge_level) / usable_capacity
    available_energy = charge_level - min_charge_level
    
    if info_logger:
        info_logger.info(f"  BESS: {charge_level:.2f}/{max_charge_level:.2f} kWh")
        info_logger.info(f"  Charge: {charge_percent*100:.1f}% | Available: {available_energy:.2f} kWh")
    
    # USUNIĘTE: Reguła bezpieczeństwa bess_low_threshold
    # To powinno być sprawdzone WCZEŚNIEJ w check_discharge_capability()
    
    # === KROK 2: Ekonomia ===
    # Porównaj koszt zakupu vs wartość energii w BESS
    
    buy = max(tariff_buy, EPSILON)
    sell = max(tariff_sell, EPSILON)
    
    # Ratio: ile kosztuje zakup vs ile warta jest energia w BESS
    buy_sell_ratio = buy / sell
    
    if info_logger:
        info_logger.info(f"  Tariff BUY: {buy:.3f} $/kWh | SELL: {sell:.3f} $/kWh")
        info_logger.info(f"  Buy/Sell ratio: {buy_sell_ratio:.3f}")
    
    # Normalizacja ekonomii do [-1, 1]
    # ratio < 0.5 → E_buy bardzo korzystne (+1) - tania energia
    # ratio = 1.0 → neutralne (0)
    # ratio > 1.5 → E_buy bardzo niekorzystne (-1) - droga energia
    E_buy = max(-1.0, min(1.0, 1.0 - 2 * (buy_sell_ratio - 0.5)))
    E_discharge = -E_buy
    
    # === KROK 3: Stan BESS ===
    # Im więcej energii w BESS → lepiej rozładować (wykorzystaj zapas)
    # Im mniej → lepiej kupić (oszczędzaj BESS)
    
    # charge_percent = 0.5 → neutralne (0)
    # charge_percent = 1.0 → preferuj discharge (+1)
    # charge_percent = 0.0 → preferuj buy (+1)
    S_discharge = (charge_percent - 0.5) * 2  # Mapowanie 0-1 → -1 do +1
    S_discharge = max(-1.0, min(1.0, S_discharge))
    S_buy = -S_discharge
    
    # === KROK 4: Ryzyko ===
    # Ryzyko zakupu: czy blisko limitu?
    if purchase_limit is None or purchase_limit <= 0:
        R_buy = 1.0  # Brak limitu → brak ryzyka
        usage_percent = 0.0
    else:
        usage = min(1.0, bought_power / (purchase_limit + EPSILON))
        usage_percent = usage * 100.0
        # usage = 0% → R_buy = +1 (bezpiecznie)
        # usage = 100% → R_buy = -1 (niebezpiecznie)
        R_buy = 1.0 - 2.0 * usage
        R_buy = max(-1.0, min(1.0, R_buy))
    
    R_discharge = 0.0  # Rozładowanie neutralne pod względem ryzyka
    
    if info_logger:
        info_logger.debug(
            f"Risk: bought={bought_power:.2f}, limit={purchase_limit}, "
            f"usage={usage_percent:.1f}%, R_buy={R_buy:.3f}"
        )
    
    # === KROK 5: Utility ===
    U_discharge = (
        config.w1_economics * E_discharge +
        config.w2_storage * S_discharge +
        config.w3_risk * R_discharge
    )
    
    U_buy = (
        config.w1_economics * E_buy +
        config.w2_storage * S_buy +
        config.w3_risk * R_buy
    )
    
    if info_logger:
        info_logger.debug(
            f"Utility: U_discharge={U_discharge:.4f} "
            f"(E={config.w1_economics * E_discharge:.3f}, "
            f"S={config.w2_storage * S_discharge:.3f}, "
            f"R={config.w3_risk * R_discharge:.3f})"
        )
        info_logger.debug(
            f"Utility: U_buy={U_buy:.4f} "
            f"(E={config.w1_economics * E_buy:.3f}, "
            f"S={config.w2_storage * S_buy:.3f}, "
            f"R={config.w3_risk * R_buy:.3f})"
        )
    
    # === KROK 6: Bias użytkownika ===
    bias_applied = 0.0
    
    if config.mode == DecisionMode.BESS_PRIORITY:
        U_discharge += config.bias_value
        bias_applied = config.bias_value
        if info_logger:
            info_logger.info(f"Applied BESS_PRIORITY: +{config.bias_value:.2f} to U_discharge")

    elif config.mode == DecisionMode.GRID_PRIORITY:
        U_buy += config.bias_value
        bias_applied = config.bias_value
        if info_logger:
            info_logger.info(f"Applied GRID_PRIORITY: +{config.bias_value:.2f} to U_buy")
    
    # === KROK 7: Decyzja ===
    decision_discharge = U_discharge > U_buy
    utility_diff = abs(U_discharge - U_buy)
    confidence = min(1.0, utility_diff / 2.0)
    
    # === KROK 8: Uzasadnienie ===
    reason_parts = []
    
    if buy_sell_ratio < 0.75:
        reason_parts.append(f"cheap_energy(ratio={buy_sell_ratio:.2f})")
    else:
        reason_parts.append(f"expensive_energy(ratio={buy_sell_ratio:.2f})")
    
    if charge_percent > 0.70:
        reason_parts.append(f"high_charge({charge_percent*100:.1f}%)")
    elif charge_percent < 0.40:
        reason_parts.append(f"low_charge({charge_percent*100:.1f}%)")
    else:
        reason_parts.append(f"moderate_charge({charge_percent*100:.1f}%)")
    
    if usage_percent > 80:
        reason_parts.append(f"high_purchase_limit({usage_percent:.0f}%)")
    
    if config.mode != DecisionMode.AUTO:
        reason_parts.append(f"mode={config.mode.value}")
    
    reason_parts.append(f"U_discharge={U_discharge:.3f}")
    reason_parts.append(f"U_buy={U_buy:.3f}")
    
    decision_text = "DISCHARGE" if decision_discharge else "BUY"
    reason = f"{decision_text}: " + ", ".join(reason_parts)
    
    # === KROK 9: Szczegóły ===
    score_details = {
        "E_discharge": E_discharge, "E_buy": E_buy,
        "S_discharge": S_discharge, "S_buy": S_buy,
        "R_discharge": R_discharge, "R_buy": R_buy,
        "U_discharge_raw": U_discharge - bias_applied if config.mode == DecisionMode.BESS_PRIORITY else U_discharge,
        "U_buy_raw": U_buy - bias_applied if config.mode == DecisionMode.GRID_PRIORITY else U_buy,
        "U_discharge_final": U_discharge,
        "U_buy_final": U_buy,
        "buy_sell_ratio": buy_sell_ratio,
        "charge_percent": charge_percent * 100,
        "available_energy": available_energy,
        "usage_percent": usage_percent,
        "weights": {
            "w1_economics": config.w1_economics,
            "w2_storage": config.w2_storage,
            "w3_risk": config.w3_risk
        },
        "mode": config.mode.value,
        "bias_applied": bias_applied
    }
    
    # === KROK 10: Logowanie ===
    if info_logger:
        info_logger.info("-" * 70)
        info_logger.info(f"  Decision: {'DISCHARGE' if decision_discharge else 'BUY'}")
        info_logger.info(f"  Confidence: {confidence*100:.1f}%")
        info_logger.info(f"  Reason: {reason}")
        info_logger.info("=" * 70)
    
    return DecisionResult(
        decision=decision_discharge,
        reason=reason,
        confidence=confidence,
        utility_charge=U_discharge,
        utility_sell=U_buy,
        score_details=score_details
    )