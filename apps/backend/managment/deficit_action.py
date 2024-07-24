from enum import Enum


class DeficitAction(Enum):
    """
    Klasa definiująca dostępne akcje podczas zarządzania deficytem energii.
    """

    INCREASE_ACTIVE_DEVICES = 1
    ACTIVATE_INACTIVE_DEVICES = 2
    DISCHARGE_BESS = 3
    BUY_ENERGY = 4
    LIMIT_CONSUMPTION = 5
