# apps/backend/managment/energy_balance.py
from dataclasses import dataclass
from typing import Optional


@dataclass
class EnergyBalance:
    """
    Reprezentuje szczegółowy bilans energetyczny mikrosieci.
    
    Wszystkie wartości w kW (moc).
    
    SUPPLY SIDE (dostawa energii):
    - generation: Generacja ze źródeł odnawialnych/nieodnawialnych (PV, Wind, Fuel)
    - grid_import: Import energii z sieci zewnętrznej (kupno)
    - bess_discharge: Rozładowanie baterii (BESS dostarcza energię)
    
    DEMAND SIDE (zapotrzebowanie na energię):
    - consumption: Zużycie przez odbiorniki (loads)
    - grid_export: Eksport energii do sieci zewnętrznej (sprzedaż)
    - bess_charge: Ładowanie baterii (BESS pobiera energię)
    
    BALANCE:
    - total_supply: Suma wszystkich źródeł energii
    - total_demand: Suma wszystkich odbiorników energii
    - balance: Różnica (supply - demand)
        > 0: nadwyżka energii
        < 0: deficyt energii
        ≈ 0: bilans zrównoważony
    """
    
    # === SUPPLY SIDE ===
    generation: float  # kW - Generacja (PV, Wind, Fuel Turbine, Fuel Cell)
    grid_import: float  # kW - Import z sieci (kupno)
    bess_discharge: float  # kW - Rozładowanie BESS (gdy actual_output > 0)
    
    # === DEMAND SIDE ===
    consumption: float  # kW - Zużycie odbiorników
    grid_export: float  # kW - Eksport do sieci (sprzedaż)
    bess_charge: float  # kW - Ładowanie BESS (gdy actual_output < 0)
    
    # === TOTALS ===
    total_supply: float  # kW - Suma podaży
    total_demand: float  # kW - Suma popytu
    balance: float  # kW - Różnica (supply - demand)
    
    # === CONVENIENCE PROPERTIES ===
    @property
    def surplus(self) -> float:
        """Nadwyżka energii (jeśli balance > 0)"""
        return max(0, self.balance)
    
    @property
    def deficit(self) -> float:
        """Deficyt energii (jeśli balance < 0)"""
        return max(0, -self.balance)
    
    def is_balanced(self, threshold: float = 1.0) -> bool:
        """
        Sprawdza czy system jest zbalansowany.
        
        Args:
            threshold: Próg tolerancji w kW (domyślnie 1 kW)
        
        Returns:
            True jeśli |balance| < threshold
        """
        return abs(self.balance) < threshold
    
    @property
    def has_surplus(self) -> bool:
        """Czy jest nadwyżka energii?"""
        return self.balance > 0
    
    @property
    def has_deficit(self) -> bool:
        """Czy jest deficyt energii?"""
        return self.balance < 0
    
    def __str__(self) -> str:
        """Czytelna reprezentacja tekstowa"""
        return (
            f"EnergyBalance(\n"
            f"  SUPPLY: {self.total_supply:.2f} kW\n"
            f"    - Generation:    {self.generation:.2f} kW\n"
            f"    - Grid Import:   {self.grid_import:.2f} kW\n"
            f"    - BESS Discharge:{self.bess_discharge:.2f} kW\n"
            f"  DEMAND: {self.total_demand:.2f} kW\n"
            f"    - Consumption:   {self.consumption:.2f} kW\n"
            f"    - Grid Export:   {self.grid_export:.2f} kW\n"
            f"    - BESS Charge:   {self.bess_charge:.2f} kW\n"
            f"  BALANCE: {self.balance:+.2f} kW {'(SURPLUS)' if self.has_surplus else '(DEFICIT)' if self.has_deficit else '(OK)'}\n"
            f")"
        )
    
    def to_dict(self) -> dict:
        """Konwersja do słownika (dla JSON/API)"""
        return {
            "supply": {
                "generation": round(self.generation, 2),
                "grid_import": round(self.grid_import, 2),
                "bess_discharge": round(self.bess_discharge, 2),
                "total": round(self.total_supply, 2)
            },
            "demand": {
                "consumption": round(self.consumption, 2),
                "grid_export": round(self.grid_export, 2),
                "bess_charge": round(self.bess_charge, 2),
                "total": round(self.total_demand, 2)
            },
            "balance": {
                "value": round(self.balance, 2),
                "surplus": round(self.surplus, 2),
                "deficit": round(self.deficit, 2),
                "is_balanced": self.is_balanced()  # ✅ Wywołaj jako metodę!
            }
        }