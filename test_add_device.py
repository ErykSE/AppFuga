import pytest
import json
from apps.backend.managment.micro_grid_class import Microgrid
from apps.backend.devices.pv_class import PV
from apps.backend.devices.wind_turbine_class import WindTurbine
from apps.backend.devices.fuel_turbine_class import FuelTurbine
from apps.backend.devices.fuel_cell_class import FuelCell
from apps.backend.devices.bess_class import BESS


@pytest.fixture
def initial_data():
    return {
        "pv_panels": [
            {
                "id": 1,
                "name": "PV Panel 1",
                "priority": 1,
                "max_output": 100,
                "min_output": 10,
                "actual_output": 50,
                "switch_status": False,
                "device_status": "offline",
            },
            {
                "id": 2,
                "name": "PV Panel 2",
                "priority": 1,
                "max_output": 120,
                "min_output": 15,
                "actual_output": 30,
                "switch_status": True,
                "device_status": "online",
            },
        ],
        "wind_turbines": [
            {
                "id": 1,
                "name": "Wind Turbine 1",
                "priority": 1,
                "max_output": 200,
                "min_output": 20,
                "actual_output": 150,
                "switch_status": True,
                "device_status": "online",
            },
            {
                "id": 2,
                "name": "Wind Turbine 2",
                "priority": 1,
                "max_output": 180,
                "min_output": 20,
                "actual_output": 100,
                "switch_status": False,
                "device_status": "offline",
            },
        ],
        "fuel_turbines": [
            {
                "id": 1,
                "name": "Fuel Turbine 1",
                "priority": 1,
                "max_output": 300,
                "min_output": 30,
                "actual_output": 250,
                "switch_status": True,
                "device_status": "online",
            }
        ],
        "fuel_cells": [
            {
                "id": 1,
                "name": "Fuel Cell 1",
                "priority": 1,
                "max_output": 150,
                "min_output": 15,
                "actual_output": 120,
                "switch_status": True,
                "device_status": "online",
            }
        ],
        "bess": [
            {
                "id": 1,
                "name": "BESS 1",
                "capacity": 500,
                "charge_level": 200,
                "switch_status": True,
                "device_status": "online",
            },
            {
                "id": 2,
                "name": "BESS 2",
                "capacity": 300,
                "charge_level": 150,
                "switch_status": True,
                "device_status": "online",
            },
        ],
    }


@pytest.fixture
def microgrid(initial_data, tmp_path):
    # Tworzymy tymczasowy plik JSON z danymi
    json_file = tmp_path / "initial_data.json"
    with open(json_file, "w") as f:
        json.dump(initial_data, f)

    # Tworzymy instancję Microgrid i ładujemy dane
    mg = Microgrid()
    mg.load_data_from_json(str(json_file))
    return mg


def test_pv_panels_added(microgrid, initial_data):
    assert len(microgrid.pv_panels) == len(initial_data["pv_panels"])
    for i, panel in enumerate(microgrid.pv_panels):
        assert isinstance(panel, PV)
        assert panel.id == initial_data["pv_panels"][i]["id"]
        assert panel.name == initial_data["pv_panels"][i]["name"]


def test_wind_turbines_added(microgrid, initial_data):
    assert len(microgrid.wind_turbines) == len(initial_data["wind_turbines"])
    for i, turbine in enumerate(microgrid.wind_turbines):
        assert isinstance(turbine, WindTurbine)
        assert turbine.id == initial_data["wind_turbines"][i]["id"]
        assert turbine.name == initial_data["wind_turbines"][i]["name"]


def test_fuel_turbines_added(microgrid, initial_data):
    assert len(microgrid.fuel_turbines) == len(initial_data["fuel_turbines"])
    for i, turbine in enumerate(microgrid.fuel_turbines):
        assert isinstance(turbine, FuelTurbine)
        assert turbine.id == initial_data["fuel_turbines"][i]["id"]
        assert turbine.name == initial_data["fuel_turbines"][i]["name"]


def test_fuel_cells_added(microgrid, initial_data):
    assert len(microgrid.fuel_cells) == len(initial_data["fuel_cells"])
    for i, cell in enumerate(microgrid.fuel_cells):
        assert isinstance(cell, FuelCell)
        assert cell.id == initial_data["fuel_cells"][i]["id"]
        assert cell.name == initial_data["fuel_cells"][i]["name"]


def test_bess_added(microgrid, initial_data):
    assert len(microgrid.bess) == len(initial_data["bess"])
    for i, bess in enumerate(microgrid.bess):
        assert isinstance(bess, BESS)
        assert bess.id == initial_data["bess"][i]["id"]
        assert bess.name == initial_data["bess"][i]["name"]


def test_total_power_generated(microgrid, initial_data):
    expected_power = sum(
        device["actual_output"]
        for device_list in [
            initial_data["pv_panels"],
            initial_data["wind_turbines"],
            initial_data["fuel_turbines"],
            initial_data["fuel_cells"],
        ]
        for device in device_list
    )
    assert microgrid.total_power_generated() == expected_power


def test_get_active_devices(microgrid):
    active_devices = microgrid.get_active_devices()
    assert all(device.get_status() == "online" for device in active_devices)


def test_get_inactive_devices(microgrid):
    inactive_devices = microgrid.get_inactive_devices()
    assert all(device.get_status() == "offline" for device in inactive_devices)


import pytest


@pytest.mark.parametrize(
    "device_type", ["pv_panels", "wind_turbines", "fuel_turbines", "fuel_cells"]
)
def test_device_output_range(microgrid, initial_data, device_type):
    for device in getattr(microgrid, device_type):
        initial_device = next(
            d for d in initial_data[device_type] if d["id"] == device.id
        )
        assert (
            device.min_output <= device.actual_output <= device.max_output
        ), f"{device.name} output out of range"
        assert (
            device.min_output == initial_device["min_output"]
        ), f"{device.name} min_output mismatch"
        assert (
            device.max_output == initial_device["max_output"]
        ), f"{device.name} max_output mismatch"
        assert (
            device.actual_output == initial_device["actual_output"]
        ), f"{device.name} actual_output mismatch"


def test_bess_charge_level(microgrid, initial_data):
    for bess in microgrid.bess:
        initial_bess = next(b for b in initial_data["bess"] if b["id"] == bess.id)
        assert (
            0 <= bess.charge_level <= bess.capacity
        ), f"{bess.name} charge level out of range"
        assert (
            bess.capacity == initial_bess["capacity"]
        ), f"{bess.name} capacity mismatch"
        assert (
            bess.charge_level == initial_bess["charge_level"]
        ), f"{bess.name} charge_level mismatch"


def test_device_status_consistency(microgrid):
    for device in microgrid.get_all_devices():
        assert device.switch_status == (
            device.get_status() == "online"
        ), f"{device.name} status inconsistent"


def test_reasonable_power_values(microgrid):
    for device in microgrid.get_all_devices():
        if hasattr(device, "max_output"):
            assert (
                0 <= device.max_output <= 1000
            ), f"{device.name} has unreasonable max_output"
        if hasattr(device, "min_output"):
            assert (
                0 <= device.min_output <= device.max_output
            ), f"{device.name} has unreasonable min_output"


"""
def test_unique_device_ids(microgrid):
    all_ids = [device.id for device in microgrid.get_all_devices()]
    assert len(all_ids) == len(set(all_ids)), "Duplicate device IDs found"
"""


def test_json_data_integrity(initial_data):
    required_fields = {
        "pv_panels": [
            "id",
            "name",
            "priority",
            "max_output",
            "min_output",
            "actual_output",
            "switch_status",
            "device_status",
        ],
        "wind_turbines": [
            "id",
            "name",
            "priority",
            "max_output",
            "min_output",
            "actual_output",
            "switch_status",
            "device_status",
        ],
        "fuel_turbines": [
            "id",
            "name",
            "priority",
            "max_output",
            "min_output",
            "actual_output",
            "switch_status",
            "device_status",
        ],
        "fuel_cells": [
            "id",
            "name",
            "priority",
            "max_output",
            "min_output",
            "actual_output",
            "switch_status",
            "device_status",
        ],
        "bess": [
            "id",
            "name",
            "capacity",
            "charge_level",
            "switch_status",
            "device_status",
        ],
    }

    for device_type, fields in required_fields.items():
        for device in initial_data[device_type]:
            for field in fields:
                assert field in device, f"Missing {field} in {device_type}"
