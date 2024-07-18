import pytest
import json
from unittest.mock import mock_open, patch
from apps.backend.microgrid import Microgrid
from apps.backend.devices.pv_class import PV
from apps.backend.devices.wind_turbine_class import WindTurbine
from apps.backend.devices.fuel_turbine_class import FuelTurbine
from apps.backend.devices.fuel_cell_class import FuelCell
from apps.backend.devices.bess_class import BESS


@pytest.fixture
def sample_json_data():
    return {
        "pv_panels": [
            {
                "id": 1,
                "name": "PV Panel 1",
                "priority": 1,
                "max_output": 100,
                "min_output": 0,
                "actual_output": 50,
                "switch_status": True,
                "device_status": "online",
            }
        ],
        "wind_turbines": [
            {
                "id": 2,
                "name": "Wind Turbine 1",
                "priority": 2,
                "max_output": 200,
                "min_output": 10,
                "actual_output": 150,
                "switch_status": True,
                "device_status": "online",
            }
        ],
        "fuel_turbines": [
            {
                "id": 3,
                "name": "Fuel Turbine 1",
                "priority": 3,
                "max_output": 300,
                "min_output": 50,
                "actual_output": 200,
                "switch_status": True,
                "device_status": "online",
            }
        ],
        "fuel_cells": [
            {
                "id": 4,
                "name": "Fuel Cell 1",
                "priority": 4,
                "max_output": 150,
                "min_output": 20,
                "actual_output": 100,
                "switch_status": True,
                "device_status": "online",
            }
        ],
        "bess_units": [
            {
                "id": 5,
                "name": "BESS 1",
                "priority": 5,
                "max_output": 500,
                "min_output": 0,
                "actual_output": 0,
                "switch_status": True,
                "device_status": "online",
                "charge_level": 400,
            }
        ],
    }


@pytest.fixture
def microgrid():
    return Microgrid()


def test_load_data_from_json(microgrid, sample_json_data):
    # Mockujemy funkcję open(), aby symulować odczyt z pliku
    with patch("builtins.open", mock_open(read_data=json.dumps(sample_json_data))):
        microgrid.load_data_from_json("fake_path.json")

    # Sprawdzamy, czy odpowiednia liczba urządzeń została dodana
    assert len(microgrid.pv_panels) == 1
    assert len(microgrid.wind_turbines) == 1
    assert len(microgrid.fuel_turbines) == 1
    assert len(microgrid.fuel_cells) == 1
    assert len(microgrid.bess_units) == 1

    # Sprawdzamy, czy urządzenia są odpowiedniego typu
    assert isinstance(microgrid.pv_panels[0], PV)
    assert isinstance(microgrid.wind_turbines[0], WindTurbine)
    assert isinstance(microgrid.fuel_turbines[0], FuelTurbine)
    assert isinstance(microgrid.fuel_cells[0], FuelCell)
    assert isinstance(microgrid.bess_units[0], BESS)

    # Sprawdzamy, czy dane zostały poprawnie załadowane dla jednego urządzenia każdego typu
    pv = microgrid.pv_panels[0]
    assert pv.id == 1
    assert pv.name == "PV Panel 1"
    assert pv.max_output == 100
    assert pv.actual_output == 50

    wind = microgrid.wind_turbines[0]
    assert wind.id == 2
    assert wind.name == "Wind Turbine 1"
    assert wind.max_output == 200
    assert wind.actual_output == 150

    fuel_turbine = microgrid.fuel_turbines[0]
    assert fuel_turbine.id == 3
    assert fuel_turbine.name == "Fuel Turbine 1"
    assert fuel_turbine.max_output == 300
    assert fuel_turbine.actual_output == 200

    fuel_cell = microgrid.fuel_cells[0]
    assert fuel_cell.id == 4
    assert fuel_cell.name == "Fuel Cell 1"
    assert fuel_cell.max_output == 150
    assert fuel_cell.actual_output == 100

    bess = microgrid.bess_units[0]
    assert bess.id == 5
    assert bess.name == "BESS 1"
    assert bess.max_output == 500
    assert bess.actual_output == 0
    assert bess.charge_level == 400


def test_load_data_from_json_invalid_data(microgrid):
    invalid_json_data = {
        "pv_panels": [
            {
                "id": "invalid",  # Powinno być liczbą
                "name": "Invalid PV Panel",
                "priority": 1,
                "max_output": 100,
                "min_output": 0,
                "actual_output": 50,
                "switch_status": True,
                "device_status": "online",
            }
        ]
    }

    with patch("builtins.open", mock_open(read_data=json.dumps(invalid_json_data))):
        microgrid.load_data_from_json("fake_path.json")

    # Sprawdzamy, czy niepoprawne dane nie zostały dodane
    assert len(microgrid.pv_panels) == 0


def test_load_data_from_json_file_not_found(microgrid):
    with patch("builtins.open", side_effect=FileNotFoundError):
        with pytest.raises(FileNotFoundError):
            microgrid.load_data_from_json("non_existent_file.json")
