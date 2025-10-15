"""
Moduł sprawdzający możliwości operacyjne BESS.
Oblicza czy BESS może obsłużyć nadwyżkę/deficyt z uwzględnieniem limitów.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class BESSOperationPlan:
    """Plan operacji BESS."""
    
    # Czy operacja jest możliwa
    is_feasible: bool
    
    # Parametry operacji
    power_setpoint: float  # kW - moc do ustawienia (ujemna=ładowanie, dodatnia=rozładowanie)
    duration_minutes: float  # min - przewidywany czas trwania operacji
    energy_amount: float  # kWh - ilość energii do przeniesienia
    
    # Informacje o zakończeniu
    will_finish_before_next_iteration: bool  # Czy skończy się przed kolejną iteracją?
    time_to_completion_minutes: Optional[float]  # Czas do zakończenia (jeśli skończy się wcześniej)
    
    # Przyczyny niemożliwości (jeśli is_feasible=False)
    reason: Optional[str] = None


class BESSCapabilityChecker:
    """
    Klasa sprawdzająca możliwości operacyjne BESS.
    
    Uwzględnia:
    - Limity mocy (max_charge_power, max_discharge_power, min_output)
    - Limity pojemności (max_charge_level, min_charge_level)
    - Czas iteracji (czy zdąży w czasie)
    """
    
    # bess_capability_checker.py - __init__

    def __init__(self, bess, iteration_time_minutes=5, 
                bess_low_threshold=0.20,  # ← DODAJ
                info_logger=None, error_logger=None):
        self.bess = bess
        self.iteration_time_minutes = iteration_time_minutes
        self.iteration_time_hours = iteration_time_minutes / 60
        self.bess_low_threshold = bess_low_threshold  # ← DODAJ
        self.info_logger = info_logger
        self.error_logger = error_logger
    
    def check_charge_capability(self, power_surplus: float) -> BESSOperationPlan:
        """
        Sprawdza czy BESS może załadować nadwyżkę energii.
        
        Args:
            power_surplus: Nadwyżka mocy do załadowania (kW)
            
        Returns:
            BESSOperationPlan: Plan operacji ładowania
        """
        # 1. Podstawowe sprawdzenie - czy BESS włączony
        if not self.bess.switch_status:
            self._set_bess_zero_if_needed()
            return BESSOperationPlan(
                is_feasible=False,
                power_setpoint=0,
                duration_minutes=0,
                energy_amount=0,
                will_finish_before_next_iteration=False,
                time_to_completion_minutes=None,
                reason="BESS is turned off"
            )
        
        # 2. Sprawdź czy jest miejsce na ładowanie
        free_capacity = self.bess.max_charge_level - self.bess.charge_level
        if free_capacity <= 0:
            self._set_bess_zero_if_needed()
            return BESSOperationPlan(
                is_feasible=False,
                power_setpoint=0,
                duration_minutes=0,
                energy_amount=0,
                will_finish_before_next_iteration=False,
                time_to_completion_minutes=None,
                reason="BESS is already full"
            )
        
        # 3. Sprawdź limit min_output
        if power_surplus < self.bess.min_output:
            self._set_bess_zero_if_needed()
            return BESSOperationPlan(
                is_feasible=False,
                power_setpoint=0,
                duration_minutes=0,
                energy_amount=0,
                will_finish_before_next_iteration=False,
                time_to_completion_minutes=None,
                reason=f"Power surplus ({power_surplus:.2f} kW) is below min_output ({self.bess.min_output:.2f} kW)"
            )
        
        # 4. Oblicz rzeczywistą moc ładowania (ogranicz do max_charge_power)
        charge_power = min(power_surplus, self.bess.max_charge_power)
        
        # 5. Oblicz ile energii możemy załadować w czasie iteracji
        energy_in_iteration = charge_power * self.iteration_time_hours  # kWh
        
        # 6. Ogranicz do wolnej pojemności
        actual_energy = min(energy_in_iteration, free_capacity)
        
        # 7. Oblicz rzeczywisty czas ładowania
        time_to_full_hours = free_capacity / charge_power
        time_to_full_minutes = time_to_full_hours * 60
        
        # 8. Sprawdź czy skończy się przed następną iteracją
        will_finish_early = time_to_full_minutes < self.iteration_time_minutes
        
        # 9. Zwróć plan
        return BESSOperationPlan(
            is_feasible=True,
            power_setpoint=-charge_power,  # Ujemny = ładowanie
            duration_minutes=min(time_to_full_minutes, self.iteration_time_minutes),
            energy_amount=actual_energy,
            will_finish_before_next_iteration=will_finish_early,
            time_to_completion_minutes=time_to_full_minutes if will_finish_early else None,
            reason=None
        )
    
    def check_discharge_capability(self, power_deficit: float) -> BESSOperationPlan:
        """
        Sprawdza czy BESS może rozładować energię pokrywając deficyt.
        
        Args:
            power_deficit: Deficyt mocy do pokrycia (kW)
            
        Returns:
            BESSOperationPlan: Plan operacji rozładowania
        """
        # 1. Podstawowe sprawdzenie - czy BESS włączony
        if not self.bess.switch_status:
            self._set_bess_zero_if_needed()
            return BESSOperationPlan(
                is_feasible=False,
                power_setpoint=0,
                duration_minutes=0,
                energy_amount=0,
                will_finish_before_next_iteration=False,
                time_to_completion_minutes=None,
                reason="BESS is turned off"
            )
        
        # === DODAJ TUTAJ (po kroku 1) ===
    
        # Krok 2: REGUŁA BEZPIECZEŃSTWA
        usable_capacity = self.bess.max_charge_level - self.bess.min_charge_level
        current_charge_percent = (self.bess.charge_level - self.bess.min_charge_level) / usable_capacity
        
        if current_charge_percent < self.bess_low_threshold:
            self._set_bess_zero_if_needed()
            
            if self.info_logger:
                self.info_logger.warning(
                    f" BESS SAFETY: Charge too low for discharge "
                    f"({current_charge_percent*100:.1f}% < {self.bess_low_threshold*100:.0f}%)"
                )
            
            return BESSOperationPlan(
                is_feasible=False,
                power_setpoint=0,
                duration_minutes=0,
                energy_amount=0,
                will_finish_before_next_iteration=False,
                time_to_completion_minutes=None,
                reason=f"BESS charge too low ({current_charge_percent*100:.1f}% < {self.bess_low_threshold*100:.0f}%)"
            )
        
        # === KONIEC DODANEGO KODU ===
        
        # Krok 3: Sprawdź dostępną energię
        available_energy = self.bess.charge_level - self.bess.min_charge_level
        if available_energy <= 0:
            self._set_bess_zero_if_needed()
            return BESSOperationPlan(
                is_feasible=False,
                power_setpoint=0,
                duration_minutes=0,
                energy_amount=0,
                will_finish_before_next_iteration=False,
                time_to_completion_minutes=None,
                reason="BESS is at minimum charge level"
            )
        
        # 4. Sprawdź limit min_output
        if power_deficit < self.bess.min_output:
            self._set_bess_zero_if_needed()
            return BESSOperationPlan(
                is_feasible=False,
                power_setpoint=0,
                duration_minutes=0,
                energy_amount=0,
                will_finish_before_next_iteration=False,
                time_to_completion_minutes=None,
                reason=f"Power deficit ({power_deficit:.2f} kW) is below min_output ({self.bess.min_output:.2f} kW)"
            )
        
        # 5. Oblicz rzeczywistą moc rozładowania (ogranicz do max_discharge_power)
        discharge_power = min(power_deficit, self.bess.max_discharge_power)
        
        # 6. Oblicz ile energii możemy rozładować w czasie iteracji
        energy_in_iteration = discharge_power * self.iteration_time_hours  # kWh
        
        # 7. Ogranicz do dostępnej energii
        actual_energy = min(energy_in_iteration, available_energy)
        
        # 8. Oblicz rzeczywisty czas rozładowania
        time_to_empty_hours = available_energy / discharge_power
        time_to_empty_minutes = time_to_empty_hours * 60
        
        # 9. Sprawdź czy skończy się przed następną iteracją
        will_finish_early = time_to_empty_minutes < self.iteration_time_minutes
        
        # 10. Zwróć plan
        return BESSOperationPlan(
            is_feasible=True,
            power_setpoint=discharge_power,  # Dodatni = rozładowanie
            duration_minutes=min(time_to_empty_minutes, self.iteration_time_minutes),
            energy_amount=actual_energy,
            will_finish_before_next_iteration=will_finish_early,
            time_to_completion_minutes=time_to_empty_minutes if will_finish_early else None,
            reason=None
        )
    
    def _set_bess_zero_if_needed(self):
        """Ustawia setpoint BESS na 0 jeśli nie jest już zerem."""
        if self.bess.setpoint_output != 0:
            self.bess.setpoint_output = 0
            if self.info_logger:
                self.info_logger.info("BESS cannot operate - setpoint set to 0 kW")
    
    def log_plan(self, plan: BESSOperationPlan, operation_type: str):
        """
        Loguje plan operacji BESS.
        
        Args:
            plan: Plan operacji
            operation_type: Typ operacji ("charge" lub "discharge")
        """
        if not self.info_logger:
            return
        
        if not plan.is_feasible:
            self.info_logger.warning(f"BESS {operation_type} NOT FEASIBLE: {plan.reason}")
            return
        
        #self.info_logger.info("=" * 60)
        self.info_logger.info(f"BESS {operation_type.upper()} PLAN:")
        self.info_logger.info(f"  Setpoint: {plan.power_setpoint:.2f} kW")
        self.info_logger.info(f"  Energy: {plan.energy_amount:.2f} kWh")
        self.info_logger.info(f"  Duration: {plan.duration_minutes:.2f} min")
        
        if plan.will_finish_before_next_iteration:
            self.info_logger.info(f"  WARNING: Will finish in {plan.time_to_completion_minutes:.2f} min (BEFORE next iteration)")
            self.info_logger.info(f"  Early iteration will be scheduled")
        else:
            self.info_logger.info(f"  Will continue through entire iteration ({self.iteration_time_minutes} min)")
        
        #self.info_logger.info("=" * 60)