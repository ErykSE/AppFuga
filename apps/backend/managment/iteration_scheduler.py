"""
Moduł zarządzający harmonogramem iteracji algorytmu.
Umożliwia dynamiczne przyspieszenie iteracji gdy BESS kończy operację.
"""

import time
import threading
from typing import Optional
from dataclasses import dataclass


@dataclass
class ScheduledEvent:
    """Zaplanowane zdarzenie (np. zakończenie ładowania BESS)."""
    
    trigger_time: float  # Unix timestamp kiedy ma się wykonać
    event_type: str  # Typ zdarzenia (np. "bess_charge_complete")
    description: str  # Opis dla logów


class IterationScheduler:
    """
    Harmonogram iteracji z możliwością dynamicznego przyspieszenia.
    
    Przykład użycia:
        scheduler = IterationScheduler(normal_interval=300)  # 5 minut
        
        # Zaplanuj przyspieszenie za 3 minuty
        scheduler.schedule_early_iteration(
            after_seconds=180,
            event_type="bess_charge_complete",
            description="BESS will be full"
        )
        
        # W głównej pętli
        wait_time = scheduler.get_next_wait_time()
        event = scheduler.wait_for_next_iteration(wait_time)
    """
    
    def __init__(self, normal_interval_seconds=300, info_logger=None, error_logger=None):
        """
        Args:
            normal_interval_seconds: Normalny czas między iteracjami (domyślnie 5 min = 300s)
            info_logger: Logger do informacji
            error_logger: Logger do błędów
        """
        self.normal_interval = normal_interval_seconds
        self.info_logger = info_logger
        self.error_logger = error_logger
        
        self.scheduled_events = []  # Lista zaplanowanych eventów
        self.last_iteration_time = time.time()
        self.lock = threading.Lock()
    
    def schedule_early_iteration(
        self, 
        after_seconds: float, 
        event_type: str,
        description: str
    ):
        """
        Planuje przyspieszoną iterację.
        
        Args:
            after_seconds: Za ile sekund wykonać
            event_type: Typ zdarzenia (np. "bess_charge_complete")
            description: Opis dla logów
        """
        trigger_time = time.time() + after_seconds
        
        event = ScheduledEvent(
            trigger_time=trigger_time,
            event_type=event_type,
            description=description
        )
        
        with self.lock:
            self.scheduled_events.append(event)
            # Sortuj po czasie wykonania
            self.scheduled_events.sort(key=lambda e: e.trigger_time)
        
        if self.info_logger:
            self.info_logger.info(
                f"Scheduled early iteration in {after_seconds:.1f}s: {description}"
            )
    
    def get_next_wait_time(self) -> float:
        """
        Zwraca czas oczekiwania do następnej iteracji (w sekundach).
        Uwzględnia zaplanowane eventy - jeśli event jest wcześniej, zwraca krótszy czas.
        
        Returns:
            float: Czas oczekiwania w sekundach
        """
        with self.lock:
            # Jeśli są zaplanowane eventy
            if self.scheduled_events:
                next_event = self.scheduled_events[0]
                time_to_event = next_event.trigger_time - time.time()
                
                # Jeśli event jest wcześniej niż normalny interval
                if time_to_event < self.normal_interval:
                    if self.info_logger:
                        self.info_logger.info(
                            f"Next iteration accelerated to {time_to_event:.1f}s (event: {next_event.description})"
                        )
                    return max(0, time_to_event)
            
            # Normalny interval
            return self.normal_interval
    
    def check_for_triggered_events(self):
        """
        Sprawdza czy jakieś eventy powinny się wykonać teraz.
        
        Returns:
            list[ScheduledEvent]: Lista eventów do wykonania
        """
        current_time = time.time()
        triggered = []
        
        with self.lock:
            # Znajdź eventy które powinny się wykonać
            remaining = []
            for event in self.scheduled_events:
                if event.trigger_time <= current_time:
                    triggered.append(event)
                    if self.info_logger:
                        self.info_logger.info(f"Event triggered: {event.description}")
                else:
                    remaining.append(event)
            
            self.scheduled_events = remaining
        
        return triggered
    
    def clear_all_events(self):
        """Usuwa wszystkie zaplanowane eventy."""
        with self.lock:
            self.scheduled_events.clear()
        
        if self.info_logger:
            self.info_logger.info("Cleared all scheduled events")
    
    def mark_iteration_start(self):
        """Oznacza rozpoczęcie nowej iteracji."""
        self.last_iteration_time = time.time()