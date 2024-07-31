from apps.backend.devices.energy_source_class import EnergySource
from apps.backend.devices.bess_class import BESS
from apps.backend.others.osd_class import OSD
from apps.backend.devices.power_meter import PowerMeter


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
                            if isinstance(device, dict):
                                device_errors = EnergySource.validate_data(device)
                                if device_errors:
                                    errors.extend(
                                        [
                                            f"{device_type} error: {error}"
                                            for error in device_errors
                                        ]
                                    )
                            else:
                                errors.append(
                                    f"{device_type} error: Device data should be a dictionary"
                                )
                        else:
                            errors.append(f"{device_type} error: Device is None")
                else:
                    errors.append(f"{device_type} error: Expected a list of devices")

        if "bess" in data:
            bess = data["bess"]
            if isinstance(bess, list) and len(bess) > 0:
                if isinstance(bess[0], dict):
                    bess_errors = BESS.validate_data(bess[0])
                    if bess_errors:
                        errors.extend([f"BESS error: {error}" for error in bess_errors])
                else:
                    errors.append("BESS error: BESS data should be a dictionary")
            elif bess:
                errors.append("BESS error: Expected a list with one BESS device")
            else:
                errors.append("BESS error: No BESS device found")

        if "power_meters" in data:
            meters = data["power_meters"]
            if isinstance(meters, list):
                for meter in meters:
                    if meter is not None:
                        if isinstance(meter, dict):
                            meter_errors = PowerMeter.validate_data(meter)
                            if meter_errors:
                                errors.extend(
                                    [
                                        f"Power meter error: {error}"
                                        for error in meter_errors
                                    ]
                                )
                        else:
                            errors.append(
                                "Power meter error: Meter data should be a dictionary"
                            )
                    else:
                        errors.append("Power meter error: Meter is None")
            else:
                errors.append("Power meter error: Expected a list of meters")

        return errors

    @staticmethod
    def validate_contract_data(data):
        return OSD.validate_data(data)
