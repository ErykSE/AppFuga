from enum import Enum


class SurplusAction(Enum):
    """
    Klasa definiująca dostępne akcje podczas zarządzania nadwyżką energii.
    """

    CHARGE_BATTERY = 1
    SELL_ENERGY = 2
    BOTH = 3
    LIMIT_GENERATION = 4
