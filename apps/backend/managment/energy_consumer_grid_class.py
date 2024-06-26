import json

from apps.backend.devices.adjustable_devices import AdjustableDevice
from apps.backend.devices.non_adjustable import NonAdjustableDevice


class EnergyConsumerGrid:
    def __init__(self):
        self.non_adjustable_devices = []
        self.adjustable_devices = []

    def add_device(self, device, device_type):
        if device_type == "non_adjustable_device":
            if device.is_valid:
                self.non_adjustable_devices.append(device)
            else:
                print(f"Invalid Non Adjustable Device: {device.name}")
        elif device_type == "adjustable_device":
            if device.is_valid:
                self.adjustable_devices.append(device)
            else:
                print(f"Invalid Adjustable Device: {device.name}")
        else:
            print(f"Unknown device type: {device_type}")

    def update_device(self, device_data, device_type):
        for device in getattr(self, f"{device_type}s"):
            if device.id == device_data["id"]:
                for key, value in device_data.items():
                    setattr(device, key, value)
                print(f"{device.name} updated successfully.")
                return
        new_device = self.create_device_instance(device_data, device_type)
        self.add_device(new_device, device_type)

    def create_device_instance(self, device_data, device_type):
        if device_type == "non_adjustable_device":
            return NonAdjustableDevice.create_instance(device_data)
        elif device_type == "adjustable_device":
            return AdjustableDevice.create_instance(device_data)
        else:
            print(f"Unknown device type: {device_type}")
            return None

    def total_power_consumed(self):
        total_power = sum(
            device.get_current_power()
            for device in self.non_adjustable_devices
            if device.get_switch_status()
        )
        total_power += sum(
            device.get_current_power()
            for device in self.adjustable_devices
            if device.get_switch_status()
        )
        return total_power

    def load_data_from_json(self, file_path):
        with open(file_path, "r") as file:
            data = json.load(file)
        for device_type in ["non_adjustable_device", "adjustable_device"]:
            for device_data in data.get(f"{device_type}s", []):
                self.update_device(device_data, device_type)
