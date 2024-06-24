class EnergyPoint:
    def __init__(self, status, priority):
        self.status = status
        self.priority = priority

    def get_current_status(self):
        return self.connected

    def get_priority(self):
        return self.priority

    ####### Klasa dotycząca odbiorów/pól. Do zaimplementowania co ma się tutaj znaleźć dokładnie. ###############
