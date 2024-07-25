from apps.backend.devices.energy_source_class import EnergySource
from apps.backend.devices.bess_class import BESS
from apps.backend.others.osd_class import OSD


class DataValidator:
    @staticmethod
    def validate_microgrid_data(data):
        errors = []
        device_types = ["pv_panels", "wind_turbines", "fuel_turbines", "fuel_cells"]
        for device_type in device_types:
            if device_type in data:
                devices = data[device_type]
                if isinstance(devices, list):
                    for device in devices:
                        if device is not None:
                            device_errors = EnergySource.validate_data(device.__dict__)
                            if device_errors:
                                errors.extend(
                                    [
                                        f"{device_type} error: {error}"
                                        for error in device_errors
                                    ]
                                )
                        else:
                            errors.append(f"{device_type} error: Device is None")
                else:
                    errors.append(f"{device_type} error: Expected a list of devices")

        if "bess" in data:
            bess = data["bess"]
            if isinstance(bess, list) and len(bess) > 0:
                bess_errors = BESS.validate_data(bess[0].__dict__)
                if bess_errors:
                    errors.extend([f"BESS error: {error}" for error in bess_errors])
            elif bess:
                errors.append("BESS error: Expected a list with one BESS device")
            else:
                errors.append("BESS error: No BESS device found")

        # Dodaj walidację dla non_adjustable_devices i adjustable_devices

        return errors

    @staticmethod
    def validate_contract_data(data):
        return OSD.validate_data(data)
