class DeviceSet:
    def __init__(self):
        self.devices = []

    def add_device(self, device):
        self.devices.append(device)

    def remove_device(self, device):
        self.devices.remove(device)

    def total_power_generated(self):
        return sum(device.get_current_power() for device in self.devices)
